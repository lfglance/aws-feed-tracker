import re
import sys
import json
import datetime
from time import mktime

import boto3
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension

from src.models import BedrockCall



class BlankTargetTreeprocessor(Treeprocessor):
    def run(self, root):
        # Find all <a> tags in the document
        for element in root.iter('a'):
            # Add target="_blank" attribute
            element.set('target', '_blank')
        return root

class BlankTargetExtension(Extension):
    def extendMarkdown(self, md):
        # Register the treeprocessor with a priority of 10
        md.treeprocessors.register(BlankTargetTreeprocessor(md), 'blank_target', 10)

def clean_string(input_string):
    return re.sub(r'[^a-zA-Z0-9]+', '_', input_string)

def convert_to_dt(struct_time):
    return datetime.datetime.fromtimestamp(mktime(struct_time))

def query_bedrock(model_id, prompt, query, temperature=0.7, max_tokens=5000):
    bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
    body = {
        "system": [{"text": prompt}],
        "messages": [{"role": "user", "content": [{"text": query}]}]
    }
    if model_id.startswith("anthropic"):
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": query}],
            "system": prompt
        }
    elif model_id.startswith("us.amazon.nova"):
        body = {
            "system": [{"text": prompt}],
            "messages": [{"role": "user", "content": [{"text": query}]}],
            "inferenceConfig": {
                "maxTokens": max_tokens, 
                "topP": 0.9, 
                "topK": 20, 
                "temperature": temperature
            }
        }

    body = json.dumps(body)
    response = bedrock.invoke_model_with_response_stream(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body
    )
    
    return response

def handle_bedrock_response(model_id, response, print_stdout=True):
    full_response = ""
    results = {}
    if model_id.startswith("anthropic"):
        for event in response['body']:
            if "chunk" in event:
                chunk = json.loads(event["chunk"]["bytes"])
                chunk_type = chunk.get('type')
                if chunk_type == "content_block_delta":
                    text = chunk['delta'].get('text', '')
                    full_response += text
                    if print_stdout:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                elif chunk_type == "message_stop":
                    results = chunk.get("amazon-bedrock-invocationMetrics")
    elif model_id.startswith("us.amazon.nova"):
        for event in response['body']:
            if "chunk" in event:
                chunk = json.loads(event["chunk"]["bytes"])
                if "contentBlockDelta" in chunk:
                    text = chunk["contentBlockDelta"]["delta"].get("text", "")
                    full_response += text
                    if print_stdout:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                elif "amazon-bedrock-invocationMetrics" in chunk:
                    results = chunk.get("amazon-bedrock-invocationMetrics")
    
    input_tokens = results.get("inputTokenCount", 0)
    output_tokens = results.get("outputTokenCount", 0)
    br_call = BedrockCall.create(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_id=model_id
    )
    if print_stdout:
        print()
        print(f"**Input Tokens**: {input_tokens}")
        print(f"**Output Tokens**: {output_tokens}")
        print(f"**Estimated Cost**: ${br_call.calculate_cost():.6f}")

    return (full_response, results)