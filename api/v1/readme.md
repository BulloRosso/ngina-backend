# API Endpoints Documentation

## Auth Endpoints (auth.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/auth/login | POST | none | Authenticate user and get access token |
| /api/v1/auth/signup | POST | none | Register new user |
| /api/v1/auth/resend-confirmation | POST | none | Resend email confirmation link |
| /api/v1/auth/refresh | POST | none | Refresh access token using refresh token |
| /api/v1/auth/enable-mfa | POST | JWT | Enable multi-factor authentication |
| /api/v1/auth/mfa-factors | GET | JWT | List user's MFA factors |
| /api/v1/auth/validation-status/{user_id} | GET | JWT | Check email validation status |
| /api/v1/auth/request-password-reset | POST | none | Request password reset link |
| /api/v1/auth/reset-password | POST | none | Reset password using reset token |
| /api/v1/auth/profile/{user_id} | GET | JWT | Get user profile settings |
| /api/v1/auth/profile | POST | JWT | Update user profile settings |
| /api/v1/auth/verify-mfa | POST | none | Verify MFA code |
| /api/v1/auth/challenge-mfa | POST | none | Create MFA challenge |
| /api/v1/auth/mfa-level | GET | JWT | Get current MFA assurance level |

## Chat Endpoints (chat.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/chat | POST | JWT | Process chat message and get AI response |

## Interview Endpoints (interviews.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/interviews/{profile_id}/start | POST | JWT | Start new interview session |
| /api/v1/interviews/{session_id}/response | POST | JWT | Process user's interview response |
| /api/v1/interviews/{session_id}/next_question | POST | JWT | Get next interview question |
| /api/v1/interviews/{session_id}/end | POST | JWT | End interview session |
| /api/v1/interviews/{profile_id}/sessions | GET | JWT | Get all interview sessions for profile |
| /api/v1/interviews/tts/{text_to_read} | WS | none | Text-to-speech conversion |
| /api/v1/interviews/summarize | POST | JWT | Generate summaries for completed interviews |

## Memory Endpoints (memories.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/memories/memory/{memory_id} | GET | JWT | Get specific memory by ID |
| /api/v1/memories/{memory_id} | PUT | JWT | Update existing memory |
| /api/v1/memories/{profile_id} | GET | JWT | Get all memories for profile |
| /api/v1/memories | POST | JWT | Create new memory |
| /api/v1/memories/{memory_id} | DELETE | JWT | Delete memory |
| /api/v1/memories/{memory_id}/media/{filename} | DELETE | JWT | Delete media from memory |
| /api/v1/memories/{memory_id}/media | POST | JWT | Add media to memory |

## Profile Endpoints (profiles.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/profiles | GET | JWT | List all profiles for authenticated user |
| /api/v1/profiles/user/{user_id} | GET | JWT | Get all profiles for specific user |
| /api/v1/profiles | POST | JWT | Create new profile |
| /api/v1/profiles/{profile_id} | GET | JWT | Get specific profile by ID |
| /api/v1/profiles/{profile_id} | DELETE | JWT | Delete profile and associated data |
| /api/v1/profiles/rating/{profile_id} | GET | JWT | Get profile completeness rating |

## Support Bot Endpoints (supportbot.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/supportbot/bugreport | POST | JWT | Submit bug report |
| /api/v1/supportbot | POST | JWT | Get support bot response |

## Print Endpoints (print.py)

| Path | Method | Protection | Description |
|------|--------|------------|-------------|
| /api/v1/print/{profile_id} | POST | JWT | Generate and email PDF of memories |