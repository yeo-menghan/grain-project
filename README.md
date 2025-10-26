# grain-project

## Set up

```bash
uv init
uv sync
uv pip install -r requirements.txt
```

create a new folder named `./data/`, thereafter:
- Add `drivers.json` and `orders.json` under this new folder

To run backend:
```
python allocator_repeat.py
```

This will generate a new folder named `./data/attempts/` to store each LLM attempt to allocate drivers to orders. The final allocation can be found in `allocation_results.json` under `./data/` folder

This json will be utilised in the frontend. To run frontend:

```
streamlit run frontend.py
```