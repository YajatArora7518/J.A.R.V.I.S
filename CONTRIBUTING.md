# Contributing to JARVIS AI

Thank you for your interest in contributing to **JARVIS AI**! We welcome community contributions to help improve capabilities, enhance platform integrations, and optimize performance.

---

## 🛠️ Development Setup

1. **Fork and Clone** the repository:
   ```bash
   git clone https://github.com/<your-username>/JARVIS.git
   cd JARVIS
   ```

2. **Set up a Virtual Environment**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Populate .env with your Gemini / OpenRouter API keys
   ```

---

## 🧪 Testing Guidelines

Before opening a pull request, run the master verification test suite to ensure no regressions:

```bash
python tests/run_tests.py
python -m unittest tests/regression/test_baseline_regression.py
```

All 24 subsystem checks must pass.

---

## 📝 Code Conventions

- **Clean Python Style**: Adhere to PEP 8 standards with type annotations where practical.
- **Safety First**: Every new action or OS interaction must be registered with appropriate `RiskLevel` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) in `core/register_tools.py`.
- **State Verification**: Pair OS actions with deterministic verification functions in `core/verification.py`.
- **No Secrets**: Never commit API keys, personal credentials, private memory, or session files.

---

## 🚀 Pull Request Process

1. Create a new branch: `git checkout -b feature/your-feature-name`.
2. Commit your changes with clear, descriptive commit messages.
3. Push to your fork: `git push origin feature/your-feature-name`.
4. Open a Pull Request with a clear summary of your changes and test results.
