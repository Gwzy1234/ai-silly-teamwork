from pydantic import BaseModel, EmailStr, Field, SecretStr


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
        examples=["alice_chen"],
    )
    password: SecretStr = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=100, examples=["Alice"])
    email: EmailStr | None = Field(default=None, examples=["alice@example.edu"])
    invite_code: SecretStr = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50, examples=["alice_chen"])
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
