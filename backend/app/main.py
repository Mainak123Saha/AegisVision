from fastapi import FastAPI

# FastAPI application entry point (run with: uvicorn app.main:app --reload).
# Only a health-check endpoint exists so far; the video/detection pipeline is
# currently driven through app.video.demo.
app = FastAPI(title="AegisVision")


@app.get("/")
def root():
    """Health check: confirms the API is up."""
    return {"message": "AegisVision API is running"}