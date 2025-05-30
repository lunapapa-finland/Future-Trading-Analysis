.PHONY: clean performance live test_environment setup data

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_NAME = Future_Trading_Analysis
PYTHON_INTERPRETER = python


#################################################################################
# COMMANDS                                                                      #
#################################################################################



## performance
performance: setup
	@$(PYTHON_INTERPRETER) src/dashboard/utils/performance_acquisition.py
	@$(MAKE) clean >/dev/null 2>&1

## performance
data: setup
	@$(PYTHON_INTERPRETER) src/dashboard/utils/data_acquisition.py
	@$(MAKE) clean >/dev/null 2>&1

## live
live: setup performance
	@$(PYTHON_INTERPRETER) src/dashboard/app.py
	@$(MAKE) clean >/dev/null 2>&1

## Delete all compiled Python files
clean:
	@find . -type f -name "*.py[co]" -delete
	@find . -type d -name "__pycache__" -exec rm -r {} + >/dev/null 2>&1
	@find . -type d -name ".ipynb_checkpoints" -exec rm -r {} + >/dev/null 2>&1
	@find . -type d -name "build" -exec rm -r {} + >/dev/null 2>&1
	@find . -type d -name "dist" -exec rm -r {} + >/dev/null 2>&1
	@find . -type d -name "src.egg-info" -exec rm -r {} + >/dev/null 2>&1

## run setup script
setup:
	@$(PYTHON_INTERPRETER) setup.py install >/dev/null 2>&1


## Test python environment is setup correctly
test_environment:
	$(PYTHON_INTERPRETER) test_environment.py


#################################################################################
# PROJECT RULES                                                                 #
#################################################################################



#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: help
help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
