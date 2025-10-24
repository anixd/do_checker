## How to run the project

### *NOTE*: Project requires python 3.10 and higher. Tested on python 3.10.

1. create virtualenv and install deps:
```shell
python3.10 -m venv venv
```

2. activate venv:
```shell
. venv/bin/activate
```

3. Istall requirements:
```shell
pip install -r requirements.txt
````

4. edit `.env` and `.flaskenv` file (copy them from `.env.dist` and `.flaskenv.dist` and edit)

5. run migrations:
```shell
flask db upgrade
```

6. run server:
```shell
flask run
```

---
