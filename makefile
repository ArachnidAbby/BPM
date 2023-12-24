env/bin/activate: requirements.txt
	python3.11 -m venv env
	./env/bin/pip3.11 install -r requirements.txt

clean:
	rm -rf __pycache__
	rm -rf env
	rm -rf main.build/