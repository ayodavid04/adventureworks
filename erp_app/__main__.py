"""Start the demo ERP:  python -m erp_app   (then open http://localhost:4690)"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("erp_app.app:app", host="127.0.0.1", port=4690, log_level="info")
