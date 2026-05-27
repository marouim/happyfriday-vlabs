# Virtual Labs Frontend

Interface Vue 3 et Vuetify pour administrer des laboratoires virtuels self-serve.

Lancer d'abord l'API Flask depuis `../backend`, puis le frontend :

```bash
npm install
npm run dev
```

En developpement, Vite transfere `/api` vers `http://127.0.0.1:5050`.
Si le backend est expose sur une URL distincte au build, definir
`VITE_API_BASE_URL` en se basant sur `.env.example`.

Pour generer la version de production :

```bash
npm run build
```

## Deploiement OpenShift avec S2I

L'application est construite par l'image Node.js S2I grace au script `postinstall`,
puis servie sur le port `8080` par le script `start`.

Les templates creent un `BuildConfig` S2I, un `ImageStream`, un `Deployment`,
un `Service` et une `Route` HTTPS pour le seul frontend. Le backend Flask est
deploye separement depuis `../backend`; sa route publique est obligatoire
pour construire les assets Vite.

### Depuis le dossier local

Ce mode envoie directement les sources du dossier courant a OpenShift :

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

BACKEND_URL=https://$(oc get route virtual-labs-backend -o jsonpath='{.spec.host}')
oc process -f openshift/binary-template.yaml \
  -p BACKEND_BASE_URL=${BACKEND_URL} \
  | oc apply -f -
oc start-build virtual-labs-frontend --from-dir=. --follow
oc get route virtual-labs-frontend
```

Une construction binaire doit etre relancee avec `--from-dir=.` apres chaque
modification locale. Le fichier `.s2iignore` evite de televerser les
dependances locales et l'ancien dossier `dist`.

### Depuis un depot Git

Pour que le cluster relance les builds depuis un depot accessible :

```bash
oc login https://api.example.openshift.com:6443
oc project my-project

oc process -f openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=https://github.com/example/virtual-labs-frontend.git \
  -p SOURCE_REPOSITORY_REF=main \
  -p BACKEND_BASE_URL=https://virtual-labs-backend-my-project.apps.example.com \
  | oc apply -f -

oc start-build virtual-labs-frontend --follow
oc get route virtual-labs-frontend
```

Si le projet reside dans un sous-dossier du depot, fournir aussi
`-p CONTEXT_DIR=frontend`.

Le tag S2I configure par defaut dans les deux templates est `nodejs:20-ubi8`
du namespace `openshift`. S'il n'existe pas sur le cluster, fournir un tag
disponible :

```bash
oc get imagestreamtag -n openshift | grep nodejs
oc process -f openshift/template.yaml \
  -p SOURCE_REPOSITORY_URL=https://github.com/example/virtual-labs-frontend.git \
  -p BACKEND_BASE_URL=https://virtual-labs-backend-my-project.apps.example.com \
  -p NODEJS_IMAGE_TAG=nodejs:20-ubi9 \
  | oc apply -f -
```

`BACKEND_BASE_URL` est injecte dans `VITE_API_BASE_URL` pendant le build S2I.
Changer la route du backend impose donc de relancer un build frontend.
