from fastapi import FastAPI
import uvicorn
import logging
logging.basicConfig(level=logging.INFO)

from app.telephony import router as telephony_router

app = FastAPI(title="Musstins Voice Agent")
app.include_router(telephony_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")