# Cloud-readiness architecture

The local deployment intentionally separates the application and database into
two services:

```text
User browser
    |
Streamlit application service
    |
Private database network
    |
MySQL service (local now; Oracle HeatWave later)
```

## Local-to-cloud mapping

| Local component | Future cloud equivalent |
| --- | --- |
| `streamlit` Compose service | Compute instance, container service, or Kubernetes workload |
| `mysql` Compose service | Oracle HeatWave or another managed database |
| `.env` values | Cloud secret manager and deployment environment variables |
| Docker health checks | Platform liveness/readiness probes |
| MySQL named volume | Managed database storage and backups |
| `chain_agent` database user | Least-privilege application identity |
| ChromaDB local directory | Managed vector database or durable private storage |
| Hugging Face Docker volume | Model cache or a prebuilt model image |

## Deployment boundaries

The Streamlit service should be the only public-facing component. The database
should remain on a private network and accept connections only from the
application service. Database credentials must never be committed to Git or
baked into the Docker image.

Before cloud deployment, replace local development values with managed
secrets, restrict inbound traffic, enable TLS, configure backups, and decide
whether ChromaDB will remain local to the application or move to a managed
vector store.
