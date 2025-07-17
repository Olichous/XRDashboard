# XR Dashboard

This is a minimal proof of concept for managing IOS-XR equipment. It features:

- Inventory listing with reachability check
- Upload area for software images
- Basic update scheduling
- Real-time console logs during updates

## Running

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python db_create.py
python app.py
```

Or build the Docker image:

```bash
docker build -t xrdashboard .
```
