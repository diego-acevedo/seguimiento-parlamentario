init:
	export $(cat .env | xargs)
	pip install -e .