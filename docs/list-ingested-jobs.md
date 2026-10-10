# `GET /api/jobs/ingested/`

Paginated list of ingested jobs (from the ScuibJobsAi pipeline).

- **Route name:** `list-ingested-jobs`
- **View:** `api/job_handoff_views.py` → `list_ingested_jobs`
- **Auth:** none (`AllowAny`) — no `Authorization` header required.
- Also exposed in the auto-generated Swagger UI at `/swagger/` (and ReDoc at `/redoc/`).

---

## Query parameters

| Param       | Type   | Required | Default | Notes |
|-------------|--------|----------|---------|-------|
| `page`      | int    | no       | `1`     | 1-based page number. Values `< 1` or non-numeric fall back to `1`. |
| `page_size` | int    | no       | `50`    | Items per page. Capped at `200`. Values `< 1` or non-numeric fall back to `50`. |
| `limit`     | int    | no       | —       | **Alias for `page_size`** (kept for backwards compatibility). Ignored if `page_size` is present. |
| `status`    | string | no       | —       | Filter by job status, e.g. `pending` or `matched`. |

Results are ordered newest first: `-created_at`, tie-broken by `-id`.

---

## Examples

### curl

```bash
# First page, default size (50)
curl "https://<host>/api/jobs/ingested/"

# Page 3, 20 items per page, only matched jobs
curl "https://<host>/api/jobs/ingested/?page=3&page_size=20"
```

### fetch

```js
const BASE = "/api";

async function fetchIngestedJobs({ page = 1, pageSize = 50, status } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (status) params.set("status", status);

  const res = await fetch(`${BASE}/jobs/ingested/?${params}`);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

const data = await fetchIngestedJobs({ page: 1, pageSize: 25, status: "matched" });
```

---

## Response

```json
{
  "count": 137,
  "page": 2,
  "page_size": 50,
  "total_pages": 3,
  "next": 3,
  "previous": 1,
  "results": [
    {
      "id": 42,
      "source_job_id": "scuib-0001",
      "title": "Backend Engineer",
      "company": "Acme Ltd",
      "location": "Lagos",
      "remote": true,
      "salary_min": 60000,
      "salary_max": 90000,
      "salary_currency": "USD",
      "required_skills": ["python", "django"],
      "preferred_skills": ["postgresql"],
      "years_experience": 3,
      "employment_type": "full-time",
      "description": "...",
      "source": "scuib_jobs_ai",
      "status": "matched",
      "match_count": 7,
      "created_at": "2026-09-21T14:03:11+00:00"
    }
  ]
}
```

### Field notes

| Field         | Meaning |
|---------------|---------|
| `count`       | **Total** number of records matching the filter — *not* the length of this page. |
| `page`        | Page number that was returned (echoed back). |
| `page_size`   | Effective page size after clamping to the max of `200`. |
| `total_pages` | `ceil(count / page_size)`; `0` when there are no records. |
| `next`        | Next page number, or `null` on the last page. |
| `previous`    | Previous page number, or `null` on the first page. |
| `results`     | Jobs for this page. **May be empty** — see below. |
| `match_count` | Number of matched users for the job (aggregated in SQL, no N+1). |

---

## Frontend pagination loop

Stop when `next` is `null` (or when `page > total_pages`):

```js
async function fetchAllIngestedJobs(status) {
  const all = [];
  let page = 1;

  for (;;) {
    const data = await fetchIngestedJobs({ page, pageSize: 100, status });
    all.push(...data.results);
    if (!data.next) break;
    page = data.next;
  }

  return all;
}
```

### UI state (e.g. for a table / infinite scroll)

```js
const { count, page, page_size, total_pages, next, previous, results } = data;

const isFirstPage = previous === null;
const isLastPage  = next === null;
const pageCount   = total_pages;
```

---

## Edge cases

- **Out-of-range page** (`?page=99` with only 3 pages): returns `200` with
  `results: []`, `next: null`, `previous: 98`, and the real `count` /
  `total_pages`. No error is raised — check `results.length`.
- **No records at all:** `count: 0`, `total_pages: 0`, `next: null`,
  `previous: null`, `results: []`.
- **Invalid params** (`?page=abc`, `?page_size=-5`): silently fall back to
  defaults (`1` / `50`) instead of returning `400`.
- **`page_size` over the cap** (`?page_size=1000`): clamped to `200`.
- **Unknown `status`:** returns an empty result set (no `400`).

---

## Related endpoints

| Method | Path                                  | Auth          | Purpose |
|--------|---------------------------------------|---------------|---------|
| POST   | `/api/jobs/ingest/`                   | `AllowAny`    | Ingest a job and run matching. |
| GET    | `/api/jobs/ingested/<id>/matches/`    | `AllowAny`    | Matched users for one job. |
| GET    | `/api/jobs/recommend/`                | `AllowAny`    | Job recommendations for a user. |
| GET    | `/api/jobs/my-matches/`               | `IsAuthenticated` | Jobs matched to the current user. |
| GET    | `/api/jobs/matched/`                  | `IsAuthenticated` | Personalized matches for current user's preferences. |
