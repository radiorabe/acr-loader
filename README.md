# ACR Loader

Loads data from ACRCloud's broadcat monitoring service and stores it
in our ownCloud instance. Runs as a cronjob and is scheduled to run
once per day.

## Usage

```
helm install my-acrloader oci://ghcr.io/radiorabe/helm/acrloader \
  --version x.y.z \
  --set acr.bearerToken=<token>,acr.projectId=<pid>,streamId=<sid> \
  --set oc.url=<url>,oc.user=<user>,oc.pass=<pass>,oc.path=<path>
```

## Development

```
python -mvenv venv
. venv/bin/activate

python -mpip install poetry

poetry install

poetry run pytest

pre-commit run
```

## License
This application is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, version 3 of the License.

## Copyright
Copyright (c) 2023 [Radio Bern RaBe](http://www.rabe.ch)
