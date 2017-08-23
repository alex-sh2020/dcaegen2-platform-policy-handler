#!/bin/bash

# org.onap.dcae
# ================================================================================
# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
# ================================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END=========================================================
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.

APPNAME=policy_handler
docker stop ${APPNAME}
docker rm ${APPNAME}
docker rmi ${APPNAME}
docker build -t ${APPNAME} .

RUNSCRIPT=$(dirname $0)/upload_config_for_ph_in_docker.sh
echo "running script ${RUNSCRIPT}"
${RUNSCRIPT}
