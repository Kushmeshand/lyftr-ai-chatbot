import os
import uvicorn

if __name__ == "__main__":
    # Render and other cloud platforms provide dynamic PORT (default 8000 for local/docker)
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
