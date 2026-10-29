# HomeCare Kenya Backend Integration

The Django application persists form submissions to its configured database. By default, local development uses
SQLite; deployments can use PostgreSQL with `DATABASE_URL`. The Django admin provides a review queue for
registrations, contribution pledges, visit requests and FoodBridge offers. New records start in a pending state and
are not treated as verified, paid, allocated or delivered.

Run database migrations after deployment:

```sh
python manage.py migrate
```

## Optional separate API

Set `HOMECARE_API_BASE_URL` to a trusted API origin, such as `https://api.example.org`, to load the home directory
from that service and send form submissions to the versioned endpoints below. Leave it unset to submit forms directly
to Django and save to the configured Django database. The API base is public configuration, not a secret. Do not put
credentials or API keys in this setting or in browser JavaScript.

| Workflow | Method and path |
| --- | --- |
| Organization registration | `POST /api/v1/home-registrations/` |
| Need submission | `POST /api/v1/needs/` |
| Contribution pledge | `POST /api/v1/contributions/` |
| FoodBridge offer | `POST /api/v1/food-offers/` |
| Visit request | `POST /api/v1/visit-requests/` |
| Home directory | `GET /api/v1/homes/` |
| Home profile | `GET /api/v1/homes/{slug}/` |

The home directory accepts `q`, `county` and `verification` query parameters. API responses for home lists may be a
JSON array or an object containing a `results` array. The home profile response may wrap its record in a `data` object.

## Form data

Requests use JSON, `snake_case` keys and stable option values. Checkboxes are sent as booleans and numeric input fields
as JSON numbers. The CSRF token is removed from the JSON body and sent in the `X-CSRFToken` header when present.

| Workflow | Request fields |
| --- | --- |
| Organization registration | `name`, `location`, `email`, `phone_number`, `website_url`, `description`, `verification_acknowledged` |
| Need submission | `home`, `title`, `category`, `quantity`, `unit`, `urgency`, `deadline`, `storage_capacity_available`, `reason` |
| Contribution pledge | `resource_type`, `direction`, `need`, `description`, `quantity`, `donor_name`, `email`, `phone_number`, `sms_consent`, `pledge_acknowledged` |
| FoodBridge offer | `food_name`, `category`, `contact_name`, `contact_email`, `quantity`, `unit`, `location`, `collection_window`, `expiry_date`, `handling`, `food_safety_confirmed` |
| Visit request | `home`, `date`, `time`, `visitor_count`, `visitor_name`, `email`, `purpose`, `notes`, `visitor_conduct_accepted` |

Return a 2xx response only after the backend has accepted and persisted the operation. For example:

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

The browser displays server-provided messages as text, never HTML. A network failure or non-2xx response is not
presented as success. A missing method or endpoint falls back to the local Django form handler; other API errors are
shown to the user rather than silently saved to a different backend.

## Stored records and review

- Organization applications are saved separately from published `ChildrenHome` records. Reviewing an application
  does not automatically publish or verify a home.
- Need submissions use `HomeNeed` and start with `verification_status=pending` and `is_published=false`. A coordinator
  must verify and explicitly publish a need before it appears to contributors or FairMatch.
- Contribution pledges are recorded as `pending_review`; they are not payments or fulfilled donations.
- FoodBridge listings and visit requests start with `status=pending_review`. Coordinator approval is separate from
  submission and does not imply that a match, visit or delivery has been confirmed.
- Contact and consent details are stored with their related submission and can be reviewed in Django admin.

## SMS notifications

Set `AT_USERNAME`, `AT_API_KEY`, and `COORDINATOR_PHONE` in the deployment environment. The coordinator receives
an SMS when a contribution pledge is submitted. Donors receive a confirmation only when they provide a phone number
in international format and explicitly consent to SMS updates.

Create and publish events in Django admin. Visitors can subscribe to event reminders on `/events/` by providing an
international-format phone number and explicit consent. Configure a daily Render Cron Job using the same environment
variables and database as the web service:

```sh
python manage.py send_event_reminders
```

The command sends a reminder once per published event, three days before its date; if a send fails or the scheduled
run is missed, it retries on later daily runs up to the event date. Subscribers can unsubscribe from `/events/`.
Keep `COORDINATOR_PHONE` and Africa's Talking credentials private; do not put them in source control or client-side
code. If `HOMECARE_API_BASE_URL` points to a separate API, that service must also store the new pledge phone/consent
fields and trigger pledge SMS itself; Django does not receive writes sent directly to that API.

## Production responsibilities

- Authenticate users and enforce organization, supplier, coordinator and administrator permissions on protected
  operations. Public form submissions should be rate-limited and reviewed.
- Use secure, same-site, HTTP-only cookies or another reviewed auth flow; do not store bearer tokens in local storage.
  For a cross-origin API, configure explicit CORS origins and credential handling.
- Validate and authorize all fields server-side. Browser required fields and consent controls are not security controls.
- Keep child records out of public and donor APIs; audit sensitive access and allocation overrides.
- Keep pledges, approved allocations, collected resources, delivered quantities and confirmed receipt as separate states.
- Create payment intents server-side with the chosen provider. Do not trust client amounts or mark money received until
  the provider confirms payment.
- Review food safety, recipient capacity, storage and delivery feasibility before approving a match. Do not allocate
  automatically.
- Return actual organization and need data only after verification and publication-permission checks.

The FairMatch screen currently renders an illustrative recommendation from the existing Python engine. Replace that
context with an authenticated recommendation endpoint when the backend contract is available; recommendations must
remain distinct from approved allocations.
