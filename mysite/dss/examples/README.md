# Example platform requests (synthetic)

Synthetic requests in the shape the Lasers4MaaS platform sends to the decision
support API, for the battery cooling plate use case. The numbers are invented
for testing and demonstration; they are not measurements.

| File | Endpoint | Role |
| --- | --- | --- |
| `pd_experiments.json` | `POST /dss/experiments/` | Process developer: compare four welding experiments |
| `pd_experiment_single.json` | `POST /dss/experiment/` | Process developer: KPIs of one experiment |
| `kam_welding_stations.json` | `POST /dss/welding-stations/` | Key account manager: compare three welding stations |
| `kam_welding_station_single.json` | `POST /dss/welding-station/` | Key account manager: KPIs of one station |

Units: `weldLength` in mm, `weldSpeed` in mm/s, powers in kW, `cycleTime` in s,
`maintenanceCosts` in €/year, material `weight` in kg per product. Consumable and
material names must match `init_data/material_data.csv`; country codes follow
Eurostat (`UK`, `EL`), as in `init_data/country_data.csv`.

Try one from the command line (development server running):

    curl -X POST http://127.0.0.1:8000/dss/welding-stations/ \
         -H "Content-Type: application/json" \
         -d @dss/examples/kam_welding_stations.json
