# Cold-Chain Logistics Assistant — System Design

## 1. Purpose

The system gives operations users one controlled interface for:

- cold-chain fleet and shipment telemetry
- current weather near a shipment corridor
- cold-chain SOP and compliance guidance

The current target is a local Docker deployment. Oracle HeatWave, EC2, and
other cloud infrastructure are future deployment options, not requirements
for R1.

## 2. High-level architecture

```text
                         User browser
                              |
                    http://localhost:8502
                              |
                  +------------------------+
                  | Streamlit application  |
                  | container              |
                  |                        |
                  | app.py                 |
                  | orchestrator.py        |
                  | agent_tools.py         |
                  +-----------+------------+
                              |
             Docker Compose private network
              /               |                \
             /                |                 \
            v                 v                  v
   +----------------+  +-------------+  +----------------+
   | MySQL          |  | ChromaDB    |  | Open-Meteo     |
   | container      |  | + BGE-M3    |  | weather API    |
   |                |  | local files |  |                |
   | telemetry      |  +-------------+  +----------------+
   | audit log      |
   +----------------+
```

The Streamlit container is the only user-facing application service. MySQL is
kept separate so database data and permissions have an independent lifecycle.

## 3. Main components

### Streamlit UI — `app.py`

Responsibilities:

- render the chat interface
- preserve the current conversation in Streamlit session state
- create a thread ID for each conversation
- send each question to the orchestrator
- display only the final business response
- show a safe generic message when an internal failure occurs

### Orchestrator — `src/orchestrator.py`

Responsibilities:

- add the system policy to each model request
- preserve conversation state with a thread ID
- bind the approved tools to the generation model
- route tool calls through the LangGraph workflow
- write one audit record per user question

The generation model is configured through environment variables. The current
implementation supports DeepSeek and OpenAI-compatible ChatOpenAI providers.

### Tool layer — `src/agent_tools.py`

The tool layer is the security and integration boundary:

| Tool | Data source | Purpose |
| --- | --- | --- |
| `query_telemetry_data` | MySQL `v_agent_fleet` view | Read approved fleet data |
| `search_compliance_sop` | Local ChromaDB | Retrieve relevant SOP chunks |
| `get_corridor_weather` | Open-Meteo | Retrieve current weather |

The telemetry tool accepts only a single `SELECT` statement against the
approved view. It cannot query the raw table or execute write operations.

### MySQL database

The database contains:

- `tbl_sc_fleet_hist_raw` — ingestion table
- `v_agent_fleet` — restricted business-facing view
- `agent_audit_log` — tool and request audit records

Database identities:

| Identity | Permission boundary |
| --- | --- |
| `chain_ingest` | Creates/replaces the raw telemetry table during ingestion |
| `chain_agent` | Reads the approved view and inserts audit records |
| root/database administrator | Local setup and administration only |

The Streamlit application uses `chain_agent`, never the root user.

### ChromaDB and BGE-M3

The SOP ingestion process:

```text
chain_logistics.md
      ↓
document chunks
      ↓
BGE-M3 embeddings
      ↓
local ChromaDB collection
```

At query time, the user question is embedded with the same BGE-M3 model and
matched against the stored SOP chunks. ChromaDB files are runtime data and are
recreated by the bootstrap process rather than committed to Git.

## 4. Request flows

### Telemetry question

```text
User question
  → Streamlit
  → orchestrator
  → generation model selects telemetry tool
  → chain_agent connects to MySQL
  → v_agent_fleet returns approved rows
  → generation model writes business response
  → audit row is inserted
  → Streamlit displays response
```

### SOP question

```text
User question
  → Streamlit
  → orchestrator
  → BGE-M3 embeds the question
  → ChromaDB returns relevant SOP chunks
  → generation model answers from retrieved context
  → audit row is inserted
  → Streamlit displays response
```

### Combined question

The agent may call more than one tool. For example, a question about a
temperature breach at a particular location may use telemetry, SOP, and
weather. The audit record stores the distinct tools used for that request.

## 5. Security design

- `.env` contains local secrets and is excluded from Git.
- Database passwords are passed as environment variables, not source code.
- The agent has no raw-table `SELECT` permission.
- The telemetry tool rejects non-`SELECT` statements, comments, and multiple
  statements.
- The agent view exposes only operational columns needed by the assistant.
- Streamlit does not expose credentials or internal architecture to users.
- The MySQL root user is used only for local initialization and administration.
- In a future deployment, MySQL should be private and reachable only from the
  application service.

## 6. Reliability and observability

Docker Compose provides:

- a MySQL health check using `mysqladmin ping`
- a Streamlit health check using the Streamlit health endpoint
- a startup dependency so Streamlit waits for healthy MySQL
- persistent MySQL storage
- persistent Hugging Face model cache

The audit table provides a basic operational trail containing:

- thread ID
- user question
- tools used
- success or error status
- timestamp
- error message when available

## 7. Local deployment lifecycle

```text
1. Start MySQL
2. Create users, role, audit table, and grants
3. Ingest telemetry with chain_ingest
4. Create or refresh v_agent_fleet
5. Embed the SOP into local ChromaDB
6. Build the Streamlit image
7. Start Streamlit after MySQL is healthy
8. Verify the UI, tools, and audit log
```

The complete sequence is available through:

```bash
bash scripts/bootstrap_local.sh
```

## 8. Future deployment boundary

The application code should remain independent of the deployment platform.
Only these boundaries should change later:

| Local R1 | Future deployment |
| --- | --- |
| Streamlit Docker container | Hosted container or managed compute service |
| MySQL Docker container | Managed MySQL or Oracle HeatWave |
| `.env` | Secret manager and environment configuration |
| Docker health checks | Platform readiness/liveness probes |
| Local ChromaDB | Durable private storage or managed vector database |
| Local network | Private cloud network and firewall rules |

The first cloud requirement should be a secure private connection between the
application service and the managed database. No cloud migration should begin
until the local contracts, permissions, and tests remain green.

## 9. R1 acceptance criteria

R1 is complete when:

- both Docker services report healthy
- the UI answers telemetry questions
- SOP search returns grounded policy context
- weather lookup returns current data or a clear service error
- out-of-scope questions receive the approved refusal
- raw-table access is denied to `chain_agent`
- every completed request creates an audit record
- automated tests pass
- a fresh local rebuild works without Oracle or EC2
