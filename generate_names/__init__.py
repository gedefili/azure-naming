# File: azure_naming_function/generate_name/__init__.py
# Version: 2.0.0
# Created: 2025-07-24
# Last Modified: 2025-07-24
# Authors: ChatGPT & Geoff DeFilippi
# Summary: HTTP-triggered Azure Function that generates SanMar-compliant names by orchestrating reusable utilities for rule lookup, name building, validation, and Azure Table storage.

import logging
import json
import azure.functions as func
from utils.naming_rules import load_naming_rule
from utils.slug import get_slug
from utils.name_generator import build_name  # fixed path
from utils.storage import check_name_exists, claim_name
from utils.validation import validate_name

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("[generate_name] Processing request to generate a compliant name.")

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    required_fields = ["resource_type", "region", "environment"]
    missing_fields = [f for f in required_fields if f not in req_body]
    if missing_fields:
        return func.HttpResponse(f"Missing fields: {', '.join(missing_fields)}", status_code=400)

    # Extract fields from the request
    resource_type = req_body["resource_type"]
    region = req_body["region"]
    environment = req_body["environment"]
    requested_by = req_body.get("requested_by", "anonymous")

    optional_inputs = {
        "system_short": req_body.get("system_short", ""),
        "domain": req_body.get("domain", ""),
        "subdomain": req_body.get("subdomain", ""),
        "index": req_body.get("index", "")
    }

    try:
        rule = load_naming_rule(resource_type)
        slug = get_slug(resource_type)
        name = build_name(region, environment, slug, rule, optional_inputs)
        validate_name(name, rule)

        if check_name_exists(region, environment, name):
            return func.HttpResponse(f"Name '{name}' is already in use.", status_code=409)

        claim_name(region, environment, name, resource_type, requested_by)

        return func.HttpResponse(
            json.dumps({
                "generated_name": name,
                "resource_type": resource_type,
                "region": region,
                "environment": environment,
                "claimed_by": requested_by
            }),
            status_code=200,
            mimetype="application/json"
        )

    except ValueError as ve:
        return func.HttpResponse(str(ve), status_code=400)
    except Exception as e:
        logging.exception("Unexpected error generating name")
        return func.HttpResponse("Internal server error.", status_code=500)
