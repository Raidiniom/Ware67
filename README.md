# Ware67

# Git Commands
## Creating a branch
```bash
git switch -c [task-type]/[task-name]
git push -u origin [task-type]/[task-name]
```

## Commit Progress
```bash
git add .
git commit -m "[message here, about progress/work]"
git push
```

# Backend
## Run
```bash
cd .\backend\
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

## Stop
```bash
ctr + c
deactivate
```

# Frontend
## Run
```bash
cd .\frontend\
npm run dev
```

## Stop
```bash
ctr + c
```