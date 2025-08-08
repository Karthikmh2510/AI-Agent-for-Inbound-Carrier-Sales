# Inbound Carrier Sales Agent – Acme Logistics

This repository contains a proof‑of‑concept **inbound carrier‑sales agent** for **Acme Logistics**. It handles carrier calls, verifies MC numbers via the FMCSA QC Mobile API, discovers relevant loads from a CSV dataset, negotiates up to three rounds, and either books the load or gracefully ends the call. The backend is built with **FastAPI**, and the solution includes a **real-time analytics dashboard** using **Streamlit**.



## Features

- **Carrier Verification (`/verify-mc`)**  
  Sanitizes the MC number, retrieves eligibility using the FMCSA API, and returns the carrier’s legal or DBA name on success.

- **Load Search (`/search-loads`)**  
  Reads `loads.csv`, parses dates into Python `datetime`, and filters on origin, destination, and equipment type. Returns matching load records including `loadboard_rate`.

- **Negotiation (`/evaluate-offer`)**  
  Looks up the board rate for a load, then:
  - Accepts the offer if it's within **15%** of board rate.
  - Counters if offer is **15–30%** lower (offer + 5% of board rate).
  - Rejects if offer is more than **30%** below the board rate.  
  Negotiations stop after three attempts.

- **Analytics (`/analytics`)**  
  Receives analytics records (offer amounts, outcomes, sentiments), sanitizes monetary fields, and exposes a GET endpoint for recent events—used to feed the dashboard.

- **Real-time Dashboard**  
  `reports/dashboard.py` uses Streamlit to display:
  - A table of recent negotiations.
  - KPIs (Total Events, Accepted, Declined).
  - Pie charts (Outcomes, Sentiment).
  - Scatter plot (Offer vs Final Rate).
  - Bar chart (Call Outcomes).  
  Includes a loading spinner and auto-refresh.

- **Security**  
  Implements API-key authentication via middleware in `main.py`, requiring `x-api-key` headers. Unauthorized requests return `401 Unauthorized` :contentReference[oaicite:1]{index=1}.

- **Environment Configuration**  
  Utilizes `python-dotenv` for environment variable management.



## Getting Started

### Prerequisites  
- Python 3.11+  
- `uvicorn`, `pip` or `uv` (via `requirements.txt`)  
- FMCSA web key (for MC verification)

### Installation Steps

```bash
git clone https://github.com/your-username/AI-Agent-for-Inbound-Carrier-Sales.git
cd AI-Agent-for-Inbound-Carrier-Sales
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Create a .env file:

Ensure the environment variables API_URL_ANALYTICS and HAPPYROBOT_REST_API_KEY are set so the dashboard can talk to your API.

```bash
HAPPYROBOT_REST_API_KEY=<your-api-key>
FMCSA_WEBKEY=<your-fmcsa-webkey>
LOADS_CSV_PATH=./data/loads.csv
OPENAI_API_KEY=     # Optional, for LLM-enablement
```

## Run the API:

``` bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

## Run the dashboard in a separate terminal:
```bash
streamlit run reports/dashboard.py
```

## Docker Usage
The repository includes a sample Dockerfile in the deployment documentation. To build and run the API in a container:

```bash
docker build -t inbound-carrier-sales:latest .
docker run -d -p 8080:8080 \ 
  -e HAPPYROBOT_REST_API_KEY=<your-key> \ 
  -e FMCSA_WEBKEY=<your-fmcsa-key> \ 
  -e LOADS_CSV_PATH=/app/data/loads.csv \ 
  inbound-carrier-sales:latest
```

## API Usage
1.	Verify a carrier:
   ```bash
 	curl -H "x-api-key: <your-key>" "http://localhost:8080/verify-mc?mc_number=123456&webkey=<fmcsa-key>"
```

2.	Search for loads:
```bash
 	curl -H "x-api-key: <your-key>" "http://localhost:8080/search-loads?origin=Detroit&destination=Denver&equipment_type=Reefer&limit=3"
```

3.	Evaluate/Negotiate an offer:
```bash
 	curl -X POST -H "Content-Type: application/json" \
     -H "x-api-key: <your-key>" \
     -d '{"load_id": "L2964", "offer": 3000, "attempts": 1}' \
     http://localhost:8080/evaluate-offer
```

4.	Record analytics (usually called by the agent script):
```bash
 	curl -X POST -H "Content-Type: application/json" \
     -H "x-api-key: <your-key>" \
     -d '{"carrier_name": "Acme Carrier", "mc_number": "123456", "offer_amount": 3000, "counter_offer_amount": 3100, "final_rate": 3050, "negotiation_outcome": "accepted", "call_outcome": "Booked", "sentiment": "Positive"}' \
     http://localhost:8080/analytics
```
---
## Project Structure

```text
│
├── data/
│ ├── creating_dataset.py
│ ├── loads.csv
│ └── loads.json
│
├── reports/
│ └── dashboard.py                       # Streamlit Dashboard UI
│
├── routes/
│ ├── analytics.py                       # /analytics endpoint
│ ├── loads.py                           # /search-loads endpoint
│ ├── negotiate_graph.py                 # Graph-based negotiation logic
│ ├── negotiate.py                       # Default negotiation handler
│ ├── testing_negotiation_graph.ipynb
│ └── verify.py                           # /verify-mc endpoint
│
├── main.py                               # FastAPI app entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                                   # Environment secrets
├── fly.toml
├── README.md
└── LICENSE
```

## Contributing
This project is a challenge solution and is not intended for production use. Pull requests that improve code quality, add unit tests, integrate databases, or enhance the negotiation logic are welcome.

## License
This repository is released under the MIT License. This repository is provided for educational purposes and does not include a license. Consult the repository owner before any commercial use.
