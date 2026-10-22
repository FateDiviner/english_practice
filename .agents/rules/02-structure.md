# 目录结构

backend/
  app/
    main.py
    core/       # config, security, deps
    models/     # SQLAlchemy models
    schemas/    # Pydantic schemas
    api/v1/     # auth, wordbooks, practice, wrong_words, stats, admin, ai
    services/   # grading, import, stats
    db/         # session, base
  alembic/
  tests/

frontend/src/
  api/ components/ layouts/ router/ stores/ styles/ views/{auth,user,admin}

规则：新文件必须放对应目录；不得在根目录创建临时脚本；单文件不超过 300 行。
