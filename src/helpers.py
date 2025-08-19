from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension

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
