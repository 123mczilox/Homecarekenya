# HomeCare Kenya Backend Integration

This frontend is server-rendered by Django and can optionally submit selected forms to a JSON API. It does not implement the API, authentication, payment processing, or persistence for the demo workflows.

## Configure the API

Set `HOMECARE_API_BASE_URL` in the Django process environment to the trusted API origin, for example `https://api.example.org`. Leave it unset to keep the current local Django preview forms. The API base is public configuration, not a secret. Do not put credentials or API keys in this setting or in browser JavaScript.

When configured, the forms submit JSON to these versioned paths:

| Workflow | Method and path |
| --- | --- |
| Organization registration | `POST /api/v1/home-registrations/` |
| Need submission | `POST /api/v1/needs/` |
| Contribution pledge | `POST /api/v1/contributions/` |
| FoodBridge offer | `POST /api/v1/food-offers/` |
| Visit request | `POST /api/v1/visit-requests/` |

The home directory currently reads from Django's `ChildrenHome` model. For a separate backend, implement `GET /api/v1/homes/` with `q`, `county`, and `verification` query parameters, plus `GET /api/v1/homes/{slug}/`, and replace the Django view data source with that API integration.

## Request and response shape

Forms send `Content-Type: application/json` and `Accept: application/json`. Request keys use `snake_case`; option values use stable identifiers, not their visible labels. `csrfmiddlewaretoken` is removed from the JSON body. When present, it is sent in the `X-CSRFToken` header.

Return a 2xx response only after the backend has accepted the operation. For example:

```json
{
  "id": "server-generated-id",
  "status": "pending_review",
  "message": "Your request was received and is awaiting review."
}
```

Return validation failures as a non-2xx response with field-level errors:

```json
{
  "detail": "Please correct the highlighted fields.",
  "errors": {
    "quantity": ["Enter a quantity greater than zero."]
  }
}
```

The browser displays server-provided messages as text, never HTML. A network failure or non-2xx response is not presented as success.

## Backend responsibilities

- Authenticate users and enforce organization, supplier, coordinator, and administrator permissions on every protected endpoint.
- Use secure, same-site, HTTP-only cookies or another reviewed auth flow; do not store bearer tokens in local storage. For a cross-origin API, configure explicit CORS origins and credential handling.
- Validate and authorize all fields server-side. The browser's required fields and consent controls are not security controls.
- Keep child records out of public and donor APIs; audit sensitive access and allocation overrides.
- Keep pledges, approved allocations, collected resources, delivered quantities, and confirmed receipt as separate states.
- Create payment intents server-side with the chosen provider. Do not trust client amounts or mark money received until the provider confirms payment. A provider checkout redirect still needs an allowlisted integration.
- Review food safety, recipient capacity, storage and delivery feasibility before approving a match. Do not allocate automatically.
- Return actual organization and need data only after verification and publication-permission checks.

The FairMatch screen currently renders a clearly labeled sample recommendation from the existing Python engine. Replace that context with an authenticated recommendation endpoint when the backend contract is available; recommendations must remain distinct from approved allocations.