tree -I 'venv|__pycache__|.git'

Dry run of removing files - see what would be removed
```
git clean -xdn
```

Execute removal of files that match pattern in gitignore
```
git clean -xdf
```