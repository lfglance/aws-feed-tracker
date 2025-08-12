# aws-feed-tracker

## Overview

Problem: Amazon Web Services is a massive hyperscaler with a constant iteration of services. It is extremely difficult for organization's to track the updates that are relevant to them such as new products, updated pricing, deprecation of services, etc. Also, there is a large variety of data sources such as RSS feeds, blogs, news sites, Linkedin Posts, etc. It is nearly impossible for people to keep up.

Solution: Aggregate all feeds and data sources of new blogs, services, posts, releases, etc, summarize them, and categorize them. Allow filtering and searching in a web interface to show only relevant updates. Offer subscriptions and notifications via email, webhook, etc.

## User Stories

As a user...
* I want to login and set preferences and define "tags" that are relevant to me
* I want a dashboard feed page showing only items relevant to me
* I want to be able to share custom dashboards

As an organization...
* I want to subscribe to alerts such as daily digest, new items, etc

## Specification

### Overview

* Development Tool: uv (0.7.19)
* Backend Language: Python
* Frontend: Server-side rendered HTML (Jinja and Flask) and HTMX Javascript
* Framework: Flask (3.1.1)
* Relational Database: SQLite (latest)
* ORM and Schema Management: peewee (3.18.2)
* AI Summarization: AWS Bedrock
* Artifact Storage: Amazon S3
* Search: Amazon Athena
* Payment Gateway: Stripe
* Product Use-case: Content aggregation, filtering, searching, notification
* RSS Feed Reader: feedparser (6.0.11)

### Aggregation Workflow

A list of URLs will be maintained which are crawled accordingly:

```
[
    "https://status.aws.amazon.com/rss/all.rss",
    "https://aws.amazon.com/blogs/aws/feed/"
]
```

Feeds will be programmatically crawled by a backend worker process and executed in a small data pipeline:

1. Retrieve RSS feed data
2. Iterate over feed items to store metadata in relational database and raw data in S3 (raw bucket)
3. Format raw data and store in S3 (formatted bucket)
4. Utilize AWS Bedrock to summarize content and store in S3 (summarized bucket)

An outdated list can be found at https://jiripik.com/2021/09/02/list-of-all-amazon-aws-rss-feeds/

### Routes

/ - home, show latest feed details for anonymous users, show pinned dashboard of logged in users
/profile - user profile management, only for authenticated users
/dashboard/<id> - show given dashboard if it is public or if it belongs to current user
/dashboard/create - create a new dashboard for the logged in user

### Free Features

Bronze will be the free tier.

* User sign-up
* User preferences
* User dashboards
* User search (within past 30 days)
* 5 dashboards per organization (email domain)

### Paid Features

Silver is the first paid tier. All bronze features, plus:

* Custom notifications per dashboard (daily digest, new items in feed)
* User search (365 days)
* 20 dashboards per organization

Gold is the second paid tier. All silver features, plus:

* 50 dashboards per organization
* User search (all-time)

### Data Models

These will evolve over time, but an initial guideline will be as followings:

```
{
    "organization": {
        "id": "string (uuid)",
        "create_date": "timestamp",
        "name": "string (company legal entity name)",
        "domain": "string (valid url)"
    },
    "user": {
        "id": "string (uuid)",
        "create_date": "timestamp",
        "email": "string (valid email address)",
        "organization": "organization id foreign key"
    },
    "tag": {
        "id": "string (uuid)",
        "create_date": "timestamp",
        "name": "string"
    },
    "page": {
        "id": "string (uuid)",
        "create_date": "timestamp",
        "title": "string (page title from rss)",
        "url": "string (url)",
        "source": "string (rss url)"
    },
    "page_tag": {
        "id": "string (uuid)",
        "tag": "tag id foreign key",
        "page": "page id foreign key"
    },
    "dashboard": {
        "id": "string (uuid)",
        "user": "user id foreign key",
        "public": "bool",
        "pinned": "bool"
    },
    "dashboard_tag": {
        "id": "string (uuid)",
        "tag": "tag id foreign key",
        "page": "page id foreign key"
    }
}
```
