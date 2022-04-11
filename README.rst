Ansible Automation Platform Billing
===================================

Captures automation usage for reporting to hyperscaler metering systems.

This module uses the Django framework (ORM) and requires a PostgreSQL database
of its own as well as at least read access to the Ansible Automation Platform controller database.

Currently supporting Azure and AWS.
  - [MS Azure Marketplace Metered Billing API](https://docs.microsoft.com/en-us/azure/marketplace/marketplace-metering-service-apis)
  - [AWS Marketplace Metering Service](https://docs.aws.amazon.com/marketplacemetering/latest/APIReference/Welcome.html)


Getting Started
---------------

To get started developing against ansible-automation-platform-azure-billing first clone a local copy of the git repository::

    git clone https://github.com/ansible/ansible-automation-platform-azure-billing.git


Change directories to the local repository::

    cd ansible-automation-platform-azure-billing


Install tox if not already present::
    
    pip install tox


Create and activate a virtual environement for development::

    tox -e venv
    source .tox/venv/bin/activate


Linting
-------

Run the linting (black, flake8, and shellcheck) via tox::

    tox -e linters


Testing
-------

Run the unit tests via tox::

    tox -e unittest


SonarQube
---------

Run static analysis and code coverage via tox.  Results posted to the
internal [Red Hat SonarQube](***REMOVED***) instance::

    tox -e sonarqube
