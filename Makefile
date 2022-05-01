# create virtual environment
.env:
	virtualenv .env

# install all needed for development
develop: .env
	.env/bin/pip install -e . -r requirements-testing.txt tox

# clean the development environment
clean:
	-rm -rf .env
