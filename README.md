# LolQuest 2023

Сайт для проведения квеста в ЛОЛ-2023.

## Запуск

### Шаг 1. Установить [Hatch](https://hatch.pypa.io)
`Hatch` - современный менеджер проектов для Python со встроенной билд-системой и менеджером окружений.

```bash
# preferred
pipx install hatch
# or (macOS)
brew install hatch
# or (not recommended)
pip install hatch
```

### Шаг 2. Поменять `flask_secret_key` в файле `config.yaml`

Вдруг среди детей найдутся эксперты по кибербезопасности.

### Шаг 3. Запустить сервер:

```bash
hatch run server -c config.yaml
```

## Разработка

### Установить [pipx](https://pypa.github.io/pipx)

MacOS:
```bash
brew install pipx
pipx ensurepath
```

Linux:
```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

### Установить [Hatch](https://hatch.pypa.io)

```bash
pipx install hatch
```

### Pre-commit hooks

```bash
pipx install pre-commit
pre-commit install
```
