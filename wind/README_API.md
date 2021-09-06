# InFraReD Deployment

A Linux-NGINX-Postgres-Python web server, containerised with Docker, managed with Docker-Compose, built for deploying machine learning models in the InFraReD (Intelligent Framework for Resilient Design) project on a single node.


## API

### Available Services

InFraReD currently offers four deep learning microclimate analysis services: wind speed, wind comfort, solar radiation, and sunlight hours. The results of these analyses are returned as a planar matrix of normalised values, so a service-specific transformation needs to be applied to these results before interpretation. Descriptions, arguments, and result transformation for each service is detailed below. Technical details can be found in the _Running Services_ section.

#### Wind Speed

The "wind speed" service predicts a plane of wind factors at the pedestrian level, given an input wind direction, and multiplies it by a given wind speed. Wind direction is expressed as an integer,
where `0` is north, `90` is east, and so on. Wind speed is expressed as a float, in meters per second. The returned normalised values need to be multiplied by the input wind speed to return results as meters per second.

#### Wind Comfort

The "wind comfort" service predicts a plane of Lawson Criteria categories, given an input wind direction and speed. 
Wind direction is expressed as an integer, where `0` is north, `90` is east, and so on. 
Wind speed is expressed as a float, in meters per second. 
The returned normalised values represent categories as seen in the following table:

| value | lawson criteria category |
| ----- | ------------------------ |
| `0.0` | "Sitting Long"           |
| `0.2` | "Sitting Short"          |
| `0.4` | "Walking Slow"           |
| `0.6` | "Walking Fast"           |
| `0.8` | "Uncomfortable"          |
| `1.0` | "Dangerous"              |

#### Solar Radiation

The "solar radiation" service predicts a plane of total yearly radiation falling on the ground. 
There are no arguments, however, note that this model was trained on the solar characteristics of Vienna, AT. 
The returned normalised values need to be multiplied by 1400 to return the results in kilowatt-hours per square meter (kWh/m^2).

#### Sunlight Hours

The "sunlight hours" service predicts a plane representing how many hours a surface recieves sunlight per day averaged over a year.
There are no arguments, however, note that this model was trained on the solar characteristics of Vienna, AT.
The returned normalised values need to be multiplied by 12 to return the results in hours per day.

### Available Routes

#### `/app`

`[GET]`: The base URI for the UnityWeb web app, the GUI of InFraReD.

#### `/api`

`[GET|POST]`: The route that handles all GraphQL requests.

### Authentication

InFraReD uses a JSON web token (JWT) and cookie based authentication system. To access the `/api` or `/app` URI's (whether that be programmatically or through the browser), you'll need the JWT stored in a cookie with the key `InFraReD`. This can be received through logging in with the GUI at the index page, or sending a POST request to the base URI (`/`) with a `username` and `password`. Clients can logout through the `/logout` route, which simply deletes this cookie.

### GraphQL

Below lists the currently available GraphQL (GQL) requests that can be made to the `/api` route. Follow [GQL's docs](https://graphql.org/learn/) for the syntax of sending a GQL request. There are two types of GQL requests: queries and mutations. Their differences, as well as what queries and mutations are currently available, are detailed below.

#### Querying Data Objects

Queries are ways a client can ask for data in the database *without* any changes. All queries need to have the `query` directive at the start of the request, as well as the return keys to be specified.

Every query will have a `success` boolean return key. Those that request for InFraReD data can have the InFraReD schema returned with the `infraredSchema` return key. There are some cases where `success` may return `true` but the `infraredSchema` is empty, and in such cases, the backend has successfully ran the request, however there is nothing found. (This is often due to an incorrect or non-existant object UUID).

##### `User`

```graphql
query {
    getUserByUuid (
        uuid: "5ea0bb9b-2599-4efb-9709-9fcc7c544ffc"
    ) {
        success
        infraredSchema
    }
}
```

##### `Project`

```graphql
query {
  getProjectsByUserUuid (
    uuid: "5ea0bb9b-2599-4efb-9709-9fcc7c544ffc"
  ) {
    success
    infraredSchema
  }
}
```

##### `Snapshot`

```graphql
query {
  getSnapshotsByProjectUuid (
    uuid: "0c0aca39-3bb9-471a-9a6f-c4ed2e9adc4e"
  ) {
    success
    infraredSchema
  }
}
```

##### `Geometry`

```graphql
query {
  getSnapshotGeometryObjects (
    uuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
  ) {
    success
    infraredSchema
  }
}
```

```graphql
query {
  getGeometryObjectByType (
    uuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
    dataObjectType: "Building"
    snapshotUuid: "0c0aca39-3bb9-471a-9a6f-c4ed2e9adc4e"
  ) {
    success
    infraredSchema
  }
}
```

#### Mutating Data Objects

Mutations are ways a client can send requests to the back and *change* the data in the database, otherwise known as "mutating" the data. All mutations need to have the `mutation` directive at the start of the request, as well as the return keys to be specified.

There are three types of mutations: `createNew_`, `delete_`, and `modify_`. The potential return keys for each of these three mutations are as follows:

| Mutation     | Return Keys       |
| ------------ | ----------------- |
| `createNew_` | `success`, `uuid` |
| `delete_`    | `success`         |
| `modify_`    | `success`         |

Another thing to note is that the arguments in the `modify_` mutation are all optional (besides `uuid`). This is so that if a data object is modified in only a few attributes (and not all of the attributes), then only the changed attributes are sent in the request. The `modify_` mutation with just the `uuid` will return `success` = `true`, however, no changes are made.

The `geometry` argument's value should follow the GeoJSON specification ([RFC7946](https://tools.ietf.org/html/rfc7946)). Note that the value is a JSONString with the quotation marks escaped (`" -> \"`).

##### `Project`

_Note: the `analysisGridResolution` currently has no effect and is here as a placeholder for future services._

```graphql
mutation {
  createNewProject (
    name: "Nariddh's First Project"
    analysisGridResolution: 10
    southWestLatitude: 48.204451
    southWestLongitude: 16.341090
    latitudeDeltaM: 300
    longitudeDeltaM: 500
    userUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
    uuid
  }
}
```

```graphql
mutation {
  deleteProject (
    uuid: "7e478a06-7352-472d-9437-7fa51101bad3"
    userUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
  }
}
```

```graphql
mutation {
  modifyProject (
    uuid: "548118bf-5165-43d6-a5da-98980338cb99"
    name: "ABC"
    description: "Project description."
    sessionSettings: "{}"
    contextBoundary: "{\"type\": \"Polygon\", \"coordinates\": [[[58.9509680562525,474.912655461642],[20.418028327353,421.223908556155],[85.3593199260642,44.9682047826234],[86.4776610491577,28.7167555728798],[86.8762776878915,23.058230609456],[105.566969145569,23.7513223325985],[104.559354845498,38.4303843495775]]]}"
    siteBoundary: "{\"type\": \"Polygon\", \"coordinates\": [[[58.9509680562525,474.912655461642],[20.418028327353,421.223908556155],[85.3593199260642,44.9682047826234],[86.4776610491577,28.7167555728798],[86.8762776878915,23.058230609456],[105.566969145569,23.7513223325985],[104.559354845498,38.4303843495775]]]}"
    analysisGridResolution: 5
    analysisProperties: "{}"
    analysisKpis: "{}"
    analysisKpiGroups: "{}"
    explorationLayout: "{}"
    southWestLatitude: 48.204452
    southWestLongitude: 16.341091
    latitudeDeltaM: 301
    longitudeDeltaM: 501
    userUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
  }
}
```

_Note: modify mutations listed here will show every argument that *can* be modified. However, as previously stated, all arguments, besides the `uuid` are optional, and can be omitted. If you are unsure about what exactly these arguments are for, best omit it from your mutation._

##### `Snapshot`

```graphql
mutation {
  createNewSnapshot (
    name: "Nariddh's First Project"
    description: "Description."
    thumbnail: "thumbnail."
    parentSnapshotUuid: "548118bf-5165-43d6-a5da-98980338cb99"
    projectUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
    uuid
  }
}
```

_Note: upon the `createNewProject` mutation, an "origin" snapshot will automatically be created_

```graphql
mutation {
  deleteSnapshot (
    uuid: "d4d8fb30-66ad-4699-ad74-eebb6c7e860e"
    projectUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
  }
}
```

```graphql
mutation {
  modifySnapshot (
    uuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
    name: "Nariddh's Snapshot 2.0"
    description: "Description."
    thumbnail: "thumbnail"
    projectUuid: "548118bf-5165-43d6-a5da-98980338cb99"
  ) {
    success
  }
}
```

##### `Building`

```graphql
mutation {
  createNewBuilding (
    use: "residential"
    height: 15
    category: "site"
    geometry: "{\"type\": \"Polygon\", \"coordinates\": [[[58.9509680562525,474.912655461642],[20.418028327353,421.223908556155],[85.3593199260642,44.9682047826234],[86.4776610491577,28.7167555728798],[86.8762776878915,23.058230609456],[105.566969145569,23.7513223325985],[104.559354845498,38.4303843495775]]]}"
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
    uuid
  }
}
```

```graphql
mutation {
  deleteBuilding(
	uuid: "31cdca26-8fb9-4e1f-92f9-95064283d519",
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
  }
}
```

```graphql
mutation {
  modifyBuilding(
    uuid: "c945ef92-7702-4844-925a-55fab8d8163d"
    use: "commercial"
    height: 5.5
    category: "context"
    geometry: "{\"type\": \"Polygon\",\"coordinates\": [[[58.9509680562525,474.912655461642],[20.418028327353,421.223908556155],[85.3593199260642,44.9682047826234],[86.4776610491577,28.7167555728798],[86.8762776878915,23.058230609456],[105.566969145569,23.7513223325985],[104.559354845498,38.4303843495775]]]}"
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
  }
}
```

##### `StreetSegment`

```graphql
mutation {
  createNewStreetSegment(
    classification: "primary"
    forwardLanes: 1
    backwardLanes: 1
    category: "site"
    geometry: "{\"type\": \"LineString\", \"coordinates\": [[58.9509681119525,474.912655461642],[20.418028327353,421.223908556155],[37.0270523782828,341.84938928469]]}"
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
    uuid
  }
}
```

```graphql
mutation {
  deleteStreetSegment(
    uuid: "bb081d90-36cd-4017-a980-01b5b5843add"
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
  }
}
```

```graphql
mutation {
  modifyStreetSegment(
    uuid: "63f9d597-24e2-4afc-9f87-101a56dbd2cc"
    classification: "secondary"
    forwardLanes: 1
    backwardLanes: 1
    category: "context"
    geometry: "{\"type\": \"LineString\", \"coordinates\": [[58.950968115632,474.912655461642],[20.418028327353,421.223908556155],[37.0270523782828,341.84938928469]]}"
    snapshotUuid: "a0e91600-50ef-47b0-9218-faef80885eb3"
  ) {
    success
  }
}
```

##### Undo

The undo mutation will only revert the three mutation types (i.e. `createNew_`, `delete_`, and `modify_`) for level-4 geometric data objects. For now, this includes `_Building` and `_StreetSegment`. Client actions are stored sequentially, so the only required argument is the `userUuid`. The response will include a `success` boolean and the modified data object within the `dataObjects` return key.

```graphql
mutation {
  undo (
    userUuid: "5ea0bb9b-2599-4efb-9709-9fcc7c544ffc"
  ) {
    success
    dataObjects
  }
}
```

#### Running Services

To run a service, there are two steps required from the client. First, request a mutation for whichever services you would like to run. This will tell the API to run the appropriate service(s), which then stores the output into the database. These mutations will return the `uuid` of the `analysis_output`, not the output itself. To retrieve the output, the client will need to query for the data stored within the database, with the `analysis_output_uuid` returned from the mutation, and the `snapshot_uuid`. The specifications for interpretting the results are seen above in the _Available Services_ section.

##### Wind Speed

```graphql
mutation {
  runServiceWindSpeed (
    snapshotUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
    analysisName: "Wind Speed 1"
    windDirection: 0
    windSpeed: 10
  ) {
    success
    uuid
  }
}
```

##### Wind Comfort

```graphql
mutation {
  runServiceWindComfort (
    snapshotUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
    analysisName: "Wind Comfort 1"
    windDirection: 0
    windSpeed: 10
  ) {
    success
    uuid
  }
}
```

##### Solar Radiation

```graphql
mutation {
  runServiceSolarRadiation (
    snapshotUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
    analysisName: "Solar Radiation 1"
  ) {
    success
    uuid
  }
}
```

##### Sunlight Hours

```graphql
mutation {
  runServiceSunlightHours (
    snapshotUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
    analysisName: "Sunlight Hours 1"
  ) {
    success
    uuid
  }
}
```

##### Querying Analysis Output Results

```graphql
query {
  getAnalysisOutput (
    uuid: "7375f83e-b32b-4401-8e49-7fe9e7ed3481"
    snapshotUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
  ) {
    success
    infraredSchema
  }
}
```

#### Exploration

Once a project has over two snapshots, a client can explore all of their snapshots through a GUI. This can be retrieved using the exploration query.

```graphql
query {
  getExploration (
    projectUuid: "2892a0c6-11c0-4a37-ad9e-9ca3f3bf63bb"
  ) {
    success
    html
  }
}
```

---

## Development

### Getting Started

To run the server locally, you'll need the Docker engine running on your machine, as well as Docker-Compose. Follow Docker's [documentation](https://docs.docker.com/install/).

Next, clone this repo, terminal into the directory, and run `docker-compose up --build`. With the containers up and running, you should be able to access the web interface by going to `127.0.0.1` or `localhost`.

To stop the containers, click `ctrl` + `c`, wait for the container to be stopped. (Don't click `ctrl` + `c` twice).

To reset the databases, run `docker-compose down -v`.

To spin the containers back up again, without any changes to the code base, use `docker-compose up`.

### Rebuilding Containers after Changes

The `docker-compose up --build` command can take a lot of time, making the testing of incremental code changes unnecessarily lengthy. Luckily, you don't need to stop, rebuild, and restart all containers. Simply rebuilding the container that has been changed, and force-recreating that container from the docker-compose file will speed up this process.

First, identify which containers need to be rebuilt. If the changes made to the codebase are contained within the `presentation` directory, the only container that needs to be rebuilt is `app-1`. To rebuild the `app-1` container, run `docker-compose build --no-cache app-1`.

And then, to see the changes on the server, recreate the container by running `docker-compose up --force-recreate -d app-1`.

### Running Tests

The back end development seeks to follow test-driven development (TDD). All tests are contained within the `tests/` directory, and can be run by running the `tests/run.sh` file.

