from fastapi import APIRouter, Depends, HTTPException
import psycopg.rows
from database import get_db
from auth import verify_password, create_access_token, get_current_user
from schemas import LoginRequest

router = APIRouter()


@router.post("/login")
def login(request: LoginRequest, db=Depends(get_db)):
    with db.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (request.username,))
        user = cur.fetchone()

    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": str(user["user_id"]), "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "department": user["department"],
        },
    }


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {k: v for k, v in current_user.items() if k != "password_hash"}
