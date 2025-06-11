from typing import List

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str = Field(
        ...,
        description="JWT access token",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        ]
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJ0eXBlIjoicmVmcmVzaCJ9.JfLPKD2taMRwOMmHcWoH6jYe1CSVPQmWzMOcvL_hsP0"
        ]
    )
    token_type: str = Field(
        ...,
        description="Token type, typically 'bearer'",
        examples=["bearer"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJ0eXBlIjoicmVmcmVzaCJ9.JfLPKD2taMRwOMmHcWoH6jYe1CSVPQmWzMOcvL_hsP0",
                    "token_type": "bearer"
                }
            ]
        }
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(
        ...,
        description="JWT refresh token",
        examples=[
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJ0eXBlIjoicmVmcmVzaCJ9.JfLPKD2taMRwOMmHcWoH6jYe1CSVPQmWzMOcvL_hsP0"
        ]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJ0eXBlIjoicmVmcmVzaCJ9.JfLPKD2taMRwOMmHcWoH6jYe1CSVPQmWzMOcvL_hsP0"
                }
            ]
        }
    }


class CreateUserRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        description="User password (8+ characters)",
        examples=["securePassword123"],
        min_length=8
    )
    role: str = Field(
        ...,
        description="User role (admin, user)",
        examples=["user", "admin"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "user@example.com",
                    "password": "securePassword123",
                    "role": "user"
                }
            ]
        }
    }


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        description="User password",
        examples=["securePassword123"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "user@example.com",
                    "password": "securePassword123"
                }
            ]
        }
    }
