# Virtual Labs

Cette application est composee de deux workloads OpenShift independants :

| Application | Sources | Image S2I | Ressources exposees |
| --- | --- | --- | --- |
| Backend Flask | `backend/` | Python | `virtual-labs-backend` (`/api/*`) |
| Frontend Vue | `frontend/` | Node.js | `virtual-labs-frontend` |

Chaque dossier contient ses propres templates `openshift/template.yaml` et
`openshift/binary-template.yaml`. Les templates produisent deux
`BuildConfig`, deux `ImageStream`, deux `Deployment` et deux conteneurs
distincts.

## Base de donnees PostgreSQL

Le backend utilise une base PostgreSQL accessible par le service `postgresql`
et les identifiants contenus dans le secret `postgresql-credentials`. La base
doit etre deployee et initialisee avant de deployer le backend.

Depuis la racine du projet, se connecter au projet OpenShift cible :

```bash
oc login https://api.example.openshift.com:6443
oc project my-project
```

Avant la premiere installation, remplacer la valeur `change-me` dans
`database/manifests/postgresql-secret.yaml` par un mot de passe adapte a
l'environnement cible. Appliquer ensuite les ressources PostgreSQL :

```bash
oc apply -f database/manifests/postgresql-secret.yaml
oc apply -f database/manifests/postgresql-pvc.yaml
oc apply -f database/manifests/postgresql-service.yaml
oc apply -f database/manifests/postgresql-deployment.yaml

oc rollout status deployment/postgresql
```

Le `PersistentVolumeClaim` `postgresql-data` conserve les donnees lors des
redemarrages du pod.

## Initialisation du schema et des donnees de base

Une fois PostgreSQL pret, executer `database/schema.sql` dans le pod :

```bash
oc exec -i deployment/postgresql -- \
  psql -v ON_ERROR_STOP=1 -U virtual_labs -d virtual_labs -f - \
  < database/schema.sql
```

Le script cree les tables `vlab_types` et `vlabs`, puis insere les types et
les laboratoires fournis comme donnees initiales. Il peut etre rejoue sans
dupliquer ces donnees. Les types de laboratoire portent aussi les numeros des
job templates AAP Start, Stop et Delete; `Airbus A320` est initialise avec
Start `8` et Stop `9`, et `Boing 737` avec Start `10` et Stop `11`.

Verifier le contenu initialise :

```bash
oc exec deployment/postgresql -- \
  psql -U virtual_labs -d virtual_labs \
  -c 'SELECT id, name FROM vlab_types ORDER BY id;'

oc exec deployment/postgresql -- \
  psql -U virtual_labs -d virtual_labs \
  -c 'SELECT id, name, status FROM vlabs ORDER BY id;'
```

Si les valeurs `POSTGRES_USER` ou `POSTGRES_DB` du secret sont modifiees,
adapter les options `-U` et `-d` dans ces commandes.

Le backend utilise aussi `starting` pendant le demarrage d'un job AAP,
`stopping` pendant l'arret, `deleting` pendant la suppression, et `failed`
quand le job AAP echoue.

## Build binaire local

Depuis la racine du projet :

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

oc process -f backend/openshift/binary-template.yaml \
  -p AAP_BASE_URL=<aap_url> \
  -p AAP_TOKEN=<token> \
  | oc apply -f -
oc start-build virtual-labs-backend --from-dir=backend --follow

BACKEND_URL=https://$(oc get route virtual-labs-backend -o jsonpath='{.spec.host}')
oc process -f frontend/openshift/binary-template.yaml \
  -p BACKEND_BASE_URL=${BACKEND_URL} \
  | oc apply -f -
oc start-build virtual-labs-frontend --from-dir=frontend --follow

oc get route virtual-labs-backend virtual-labs-frontend
```

## Build depuis un depot commun

```bash
REPOSITORY_URL=https://github.com/example/virtual-labs.git

oc process -f backend/openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=${REPOSITORY_URL} \
  -p SOURCE_REPOSITORY_REF=main \
  -p CONTEXT_DIR=backend \
  -p AAP_BASE_URL=<aap_url> \
  -p AAP_TOKEN=<token> \
  | oc apply -f -
oc start-build virtual-labs-backend --follow

BACKEND_URL=https://$(oc get route virtual-labs-backend -o jsonpath='{.spec.host}')
oc process -f frontend/openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=${REPOSITORY_URL} \
  -p SOURCE_REPOSITORY_REF=main \
  -p CONTEXT_DIR=frontend \
  -p BACKEND_BASE_URL=${BACKEND_URL} \
  | oc apply -f -
oc start-build virtual-labs-frontend --follow
```

L'URL du backend est integree au bundle Vue pendant son build. Si la route API
change, reconstruire l'image frontend.
