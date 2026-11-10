# Upgrading an existing v3.1 folder to v4.0

1. Stop the app (close the two windows, or run `.\stop_all.bat` once it exists).
2. Back up `.env` and the `data` folder (copy them somewhere safe).
3. Extract the v4.0 ZIP **over** your project folder and allow Windows to replace files.
4. Delete these v3.1 files that v4.0 no longer uses: `scripts\setup.ps1`, `scripts\start.ps1`
   (and `backend\package-lock.json` if you have one - it does not belong in the backend).
5. Keep: `.env`, `data\` (your database is upgraded automatically, no data is lost),
   `backend\.venv` (setup re-uses it and installs the new packages), `scripts\check_env.ps1`.
6. Run `powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1`, then `.\start_all.bat`.

Your old `.env` still works. New optional variables are listed in `.env.example`; note that
`LLM_MOCK_MODE` now accepts `auto` (recommended) and that `OPENAI_COMPAT_BASE_URL` should be left
blank unless you really run an OpenAI-compatible server.
