from fastapi import FastAPI

app = FastAPI(title="AegisVision")


@app.get("/")
def root():
    return {"message": "AegisVision API is running"}