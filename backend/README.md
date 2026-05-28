# Virtual Labs Backend

API Flask pour administrer les laboratoires virtuels.

La base PostgreSQL doit etre accessible localement. Depuis la racine du
projet, avec les manifests PostgreSQL deja appliques :

```bash
oc port-forward service/postgresql 5432:5432
oc exec -i deployment/postgresql -- \
  psql -U virtual_labs -d virtual_labs < database/schema.sql
```

Le script `database/schema.sql` cree les tables `vlab_types` et `vlabs`, puis
insere le jeu de donnees initial. Il est rejouable sans dupliquer les donnees.

Dans un autre terminal :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql://virtual_labs:change-me@127.0.0.1:5432/virtual_labs'
export AAP_BASE_URL='<aap_url>'
export AAP_TOKEN='<token>'
flask --app app run --debug --port 5050
```

Endpoints :

```text
GET  /api/vlabs
GET  /api/vlabtype
POST /api/vlabs
PUT  /api/vlabs/<id>
DELETE /api/vlabs/<id>
```

Quand `PUT /api/vlabs/<id>` recoit `{"status":"running"}` ou
`{"status":"stopped"}`, le backend lance le job template AAP Start ou Stop
configure sur le type du laboratoire avec un token OAuth cree dans le platform
gateway :

```text
POST ${AAP_BASE_URL}/api/controller/v2/job_templates/<aap_start_job_template_id|aap_stop_job_template_id>/launch/
```

Le backend enregistre le `job_id` retourne par AAP, place le lab en `starting`
ou `stopping`, puis surveille ce job lors des lectures `GET /api/vlabs`. Quand
AAP retourne `successful`, le statut devient la cible demandee (`running` ou
`stopped`). Si AAP retourne `failed`, `error` ou `canceled`, le statut devient
`failed`.

Selon la documentation AAP 2.6, creer ce token avec :

```bash
curl -u user:password -k -X POST \
  https://<gateway server name>/api/gateway/v1/tokens/
```

Les types `Airbus A320` et `Boing 737` sont initialises dans
`database/schema.sql` avec les job templates Start/Stop `8/9` et `10/11`.

Exemples :

```bash
curl http://127.0.0.1:5050/api/vlabs
curl http://127.0.0.1:5050/api/vlabtype
curl -X POST http://127.0.0.1:5050/api/vlabs \
  -H 'Content-Type: application/json' \
  -d '{"name":"Training lab","type":"Airbus A320"}'
curl -X PUT http://127.0.0.1:5050/api/vlabs/1 \
  -H 'Content-Type: application/json' \
  -d '{"status":"stopped"}'
curl -X DELETE http://127.0.0.1:5050/api/vlabs/1
```

Les donnees sont conservees dans PostgreSQL. En local, `DATABASE_URL` utilise
le port-forward; dans OpenShift, le `Deployment` lit les identifiants depuis
le secret `postgresql-credentials` et joint le service `postgresql`.

## Deploiement OpenShift avec S2I

Le backend est construit et execute dans son propre conteneur Python S2I,
independamment du conteneur frontend. Les templates creent un `BuildConfig`,
un `ImageStream`, un `Deployment`, un `Service` et une `Route` HTTPS.

Le fichier `.s2i/environment` configure Gunicorn avec `app:app`. Le conteneur
ecoute sur le port `8080` dans OpenShift. Le `Service` PostgreSQL, son
`Secret`, son `PVC` et le schema doivent etre installes avant le backend.

### Depuis le dossier local

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

oc process -f openshift/binary-template.yaml \
  -p AAP_BASE_URL=<aap_url> \
  -p AAP_TOKEN=<token> \
  | oc apply -f -
oc start-build virtual-labs-backend --from-dir=. --follow
oc get route virtual-labs-backend
```

Le fichier `.s2iignore` exclut l'environnement Python local des builds
binaires.

### Depuis un depot Git

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

oc process -f openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=https://github.com/example/virtual-labs-backend.git \
  -p SOURCE_REPOSITORY_REF=main \
  -p AAP_BASE_URL=<aap_url> \
  -p AAP_TOKEN=<token> \
  | oc apply -f -

oc start-build virtual-labs-backend --follow
oc get route virtual-labs-backend
```

Si le frontend et le backend partagent un depot, fournir
`-p CONTEXT_DIR=backend`.

Le tag S2I par defaut est `python:3.12-ubi8` dans le namespace `openshift`.
Utiliser un tag present sur le cluster si necessaire :

```bash
oc get imagestreamtag -n openshift | grep python
oc process -f openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=https://github.com/example/virtual-labs-backend.git \
  -p PYTHON_IMAGE_TAG=python:3.12-ubi9 \
  | oc apply -f -
```
