# Azure scoring profile: `oem-diagnosis-boost`

Use this after semantic search is configured. It boosts **troubleshooting-tagged** chunks and weights headings/paths over body text.

## Step 1 — Add index field

In **Azure Portal** → Search service → **Indexes** → `ai-agents-idx-manual-chunks-experiment` → **Fields** → **Add field**:

| Setting | Value |
|--------|--------|
| Field name | `section_tags` |
| Type | `Collection(Edm.String)` |
| Filterable | Yes |
| Facetable | Yes |
| Retrievable | Yes |
| Searchable | No |

Save the index.

## Step 2 — Create scoring profile

Open **Scoring profiles** (or **Scoring profiles** tab when editing the index) → **Add**.

| Setting | Value |
|--------|--------|
| **Name** | `oem-diagnosis-boost` |

### Text weights (field boosts)

Add weights so titles/paths rank above raw body:

| Field | Weight |
|-------|--------|
| `section_title` | 3 |
| `section_path` | 2 |
| `chapter_title` | 2 |
| `chunk_content` | 1 |

(Portal labels may say “Text weights” or per-field boost.)

### Function — tag boost

Add a **Tag** function:

| Setting | Value |
|--------|--------|
| Type | Tag |
| Field name | `section_tags` |
| Boost | 8 |
| Interpolation | Constant |
| Tags parameter name | `boostTags` |

Save the index.

## Step 3 — Re-index manuals

The pipeline now writes `section_tags` on each chunk (e.g. `troubleshooting`, `maintenance`, `safety`).

```powershell
uv run python scripts/index_manuals.py --folder .\manuals\ --manifest .\manifest.json
```

(Cached markdown is fine; no need for `--force-extract` unless you want fresh extraction.)

## Step 4 — Enable in `.env`

```env
USE_SCORING_PROFILE=true
SCORING_PROFILE_NAME=oem-diagnosis-boost
SCORING_BOOST_TAGS=troubleshooting
```

Multiple tags in `.env` use **one** Azure scoring parameter, e.g.  
`SCORING_BOOST_TAGS=maintenance,specifications,operation` → sent as  
`boostTags-maintenance,specifications,operation`.

`SCORING_BOOST_TAGS` is only sent when `USE_SCORING_PROFILE=true` **or** `SEND_SCORING_PARAMETERS=true`.  
If the profile has **only field weights** (no tag function), keep both **false** and do not send parameters.

Restart the terminal and run search:

```powershell
uv run python scripts/search_manuals.py --query "engine overheating" --manufacturer "Caterpiller"
```

## JSON reference (Edit index → JSON)

If your portal only exposes JSON, merge these fragments into the index definition:

**Field:**

```json
{
  "name": "section_tags",
  "type": "Collection(Edm.String)",
  "searchable": false,
  "filterable": true,
  "retrievable": true,
  "facetable": true
}
```

**Scoring profile:**

```json
{
  "name": "oem-diagnosis-boost",
  "text": {
    "weights": {
      "section_title": 3,
      "section_path": 2,
      "chapter_title": 2,
      "chunk_content": 1
    }
  },
  "functions": [
    {
      "type": "tag",
      "fieldName": "section_tags",
      "boost": 8,
      "interpolation": "constant",
      "tag": {
        "tagsParameter": "boostTags"
      }
    }
  ]
}
```

Add the profile to the index `"scoringProfiles": [ ... ]` array.

## Tag values written by the pipeline

| Tag | Typical source in manual |
|-----|---------------------------|
| `troubleshooting` | Path/title contains TROUBLESHOOTING, DIAGNOSTIC, FAULT, etc. |
| `maintenance` | MAINTENANCE, SERVICE DATA, … |
| `safety` | SAFETY, WARNING, CAUTION, … |
| `specifications` | SPECIFICATION, CAPACITY, … |
| `operation` | OPERATION, CONTROLS, … |
| `general` | Fallback when no rule matches |

Only tags present on a document are boosted when you pass them via `SCORING_BOOST_TAGS`.
