# ICEES Feature Variable Configuration File Format Proposal

## Introduction

The proposal is about using Dhall to combine small configuration files into one file. 

## A Very Quick Dhall Overview

The Dhall features that we use in this document:

### Records

Dhall records are like Javascript objects, with slightly different syntax, replacing `:` with `=`. For example, 

```haskell
{
   name = "AvgDailyPM2.5Exposure",
   mapping = {
     dataset = "env",
     column = "pm2.5"
   }
}
```

### Record Types
We can define types for records, Dhall checks the type to ensure that a value is well-typed. This allows us to rule out type errors such as missing fields, misspelt fields, and fields with wrong type in records. Each field can have a primitive type such as `Text`, `Bool`, `Integer`, `Number` or a record type.

For example we can define:
```haskell
{
    name: Text,
    mapping: {
        dataset: Text,
        column: Text
    },
}
```

The `:` indicates that this is a record type.

### Named Definition
We can name a definition and use it in another definition.

```haskell
let pm25mapping = {
    dataset = "env",
    column = "pm2.5"
} 
in {
   name = "AvgDailyPM2.5Exposure",
   mapping = pm25mapping
}
```

Here we name record ```{
    dataset = "env",
    column = "pm2.5"
}``` `pm25mapping`, and use it in our definition.

### Union Type

Dhall allows defining enums in the form of union types. Each alternative is allowed to have an optional value of a type. For example,

```haskell
let BinningStrategy = < Cut : Integer | QCut : Integer | NoBinning >
```
We define a type for binning strategies. `Cut` allows an integer number of binning. Same for `QCut`. `NoBinning` doesn't need any. For example, a value of this type can be `Cut 4`, `Cut 5`, `QCut 4`, or `NoBinning`.

### Function

Dhall allows defining functions similar to Javascript's lambda. Instead of using the  `x => ...` syntax, it uses the `\x : t -> ...` syntax where `t` is the type of `x`. For example,

```haskell
let cut = \ x : Integer -> Cut x
```

### Function Application

Parentheses are not needed to apply a function to a value. For example,

```cut 4```

## Feature Variables

For each ICEES variables `A`, create a `A.dhall` file. 

```haskell
let FeatureVariable = { 
    name: Text, -- variable name 
    mapping: Mapping, -- mapping 
    binning_strategies: Optional (List BinningStrategy), -- binning strategies
    feature: ICEESFeature, -- ICEES feature 
    identifiers: Identifiers -- identifiers 
} 
```

`Mapping` is defined as follow: 

```haskell
let Mapping = < GenericFHIRMapping | SpecializedFHIRMapping | EnvironmentalMapping | GEOIDMapping | NearestPointMapping | NearestFeatureMapping >
```

Currently there are six main sources FHIR-PIT maps feature variables: 
 * Generic FHIR mapping (Condition, Procedure, MedicationRequest, Observation) 
 * Specialized FHIR mapping (demographic, visit)
 * Environmental data
 * From geoid mapping (ACS) 
 * From lat, lon to nearest point (CAFO, landfill) 
 * From lat, lon to nearest feature (nearest road) 
    

We define the following six record types: 

```haskell
let GenericFHIRMapping = { 
    resource: Text, -- FHIR resource type 
    system: Text, -- FHIR system
    code: Text, -- FHIR code
    system_is_regex: Optional Bool, -- system contains a regular expression
    code_is_regex: Optional Bool -- code contains a regular expression
} 
```

For generic FHIR mappings, we match data to ICEES feature variables according to FHIR resource, system, and code. By default, if either `system` or `code` contains `*`, it is considered as a glob, which matches zero or more characters. This allows us to map, for example, ICD 10 codes such as `E50.*`. This behavior can be modified by setting the optional `system_is_regex` or `code_is_regex` fields. When they are set to `True`, the system and code are parsed as regular expressions. When they are set to `False`, the system and code are not parsed as regular expressions or globs.

```haskell
let SpecializeFHIRMapping = < Visit: FHIRMappingVisit | Age | Race | Sex | Ethnicity | Weight | Height | BMI >

let FHIRMappingVisit = List Text -- a list of diagnoses for filtering visits that count towards the ICEES feature variable
```

We enumerate specialized FHIR mappings.

```haskell
let EnvironmentalMapping = { 
    dataset: Text, -- the dataset where the data come from
    column: Text, -- the column in the dataset
    statistics: List StatisticVariant -- the statistics of the data that we calculate
}

let StatisticVariant = {
    statistic: Statistic, -- the statistic to calculate
    rename: Optional RenameAs -- optional rename of feature variable for referencing this statistic
}

let Statistic = < Max | Min | Avg | StdDev | PrevDate >

let RenameAs = < Suffix: Text | Replace: Text >
```
 
For environmental mapping, we match data from a table. We allow multiple datasets. Each dataset is referenced by its name. A column in the dataset is specified for mapping to the ICEES feature variable. A list of statistics is specified to calulate the feature variables. We support the following statistics: maximum, minimum, average, standard deviation, and previous date. Previous date is used for calculating the value the day before an encounter.

```haskell
let GEOIDMapping = { 
    dataset: Text, -- the dataset where the data come from
    column: Text, -- the column in the dataset
    datatype: FeatureType -- the type of the data
} 

let FeatureType = < string | number >
```

For geoid mapping, we match data from a table, with one column being the geoid, and other columns being the features. We allow multiple datasets, for example, ACS and ACS ur. Each dataset is referenced by its name. A column in the dataset is specified for mapping to the ICEES feature variable. A type is specified to parse the data.
 
```haskell
let NearestPointMapping = < FeatureAttribute : FeatureAttribute | Distance >

let FeatureAttribute = { 
    dataset: Text, -- the dataset where the data come from
    name: Text, -- feature attribute name
    datatype: FeatureType -- the type of the data
} 
```
 
For nearest point mapping, we match data from a shapefile. We allow mapping a special ICEES feature variable from the distance. For the nearest point, we allow mapping attributes to ICEES feature variables.

```haskell
let NearestFeatureMapping = < FeatureAttribute : FeatureAttribute | Distance >

let FeatureAttribute = { 
    dataset: Text, -- the dataset where the data come from
    name: Text, -- feature attribute name
    datatype: FeatureType -- the type of the data
} 
```
 
For nearest feature mapping, it is similar to nearest point mapping.

ICEES features are defined as follows:

```haskell
let ICEESFeature = {
    feature_type: ICEESAPIType, -- ICEES API type
    biolink_types: List Text -- biolink types
}

let ICEESAPIType = <String: TypeString | Integer : TypeInteger | Number >

let TypeInteger = {
    minimum : Optional Integer,
    maximum : Optional Integer
}

let TypeString = {
    enum : Optional (List Text)
}
```

For each icees feature, we define a feature type and a biolink type. The feature type can be `String`, `Integer`, or `Number`. For `String`, we can specify and optional list of values. For `Integer`, we can specify an optional maximum and an optional minimum.

    
Identifers are defined as follows:

```haskell
let Identifiers = List Text
```

The identifiers type is a list of identifiers.

```haskell
let BinningStrategy = {
    method: BinningMethod, -- binning method
    suffix: Optional Text -- optional suffix for feature variable referencing this binning strategy
}

let BinningMethod = < Cut : Integer | QCut : Integer | Bins : List Bin | NoBinning >

let Bin = < Range : BinRange | String : BinString >

let BinRange = {
    lower_bound: Double,
    upper_bound: Double,
    name: Text
}

let BinString = List Text
```

We support three binning strategies: equal-widthed bins, quantiles, and customized bins. For customized bins, we support bin as range or discrete bin.

## Directory Structure

The files can be stored in nested directories. They can be stored according to their biolink types as Patrick suggested. On the top level, we can have a `package.dhall`. For example:

```
config
|-package.dhall
|-Drug
| \-Prednisone.dhall
\-Disease
  |-AsthmaDx.dhall
  |-ReactiveAirwayDx.dhall
  |-DILIDx.dhall
  \-CroupDx.dhall
```

The `package.dhall` contains all feature variable references so that we can simply include one file when we assemble configurations files.

```haskell
{
   Albuterol = ./Drug/Albuterol.dhall,
   Prednisone = ./Drug/Albuterol.dhall,
   AsthmaDx = ./Disease/Asthma.dhall,
   ReactiveAirwayDx = ./Disease/Albuterol.dhall,
   CroupDx = ./Disease/CroupDx.dhall,
   DILIDx = ./Disease/DILIDx.dhall
}
```

A `combine.dhall` will be written with scripts for combining a selected list of ICEES feature variables into a configuration file. We will define three function `pit_mapping` for generating the mapping file for FHIR PIT, `icees_features` for generating icees features file for the ICEES API, and `trapi_identifiers` for generating identifiers file.

For each configuration file, a Dhall file will be written. These file are the same for every variable set. 

For mapping, create a `fhir_pit_mapping.dhall`:
```haskell
let combine = ./combine.dhall
let variables = ./variables.dhall
in combine pit_mapping variables
```
For identifiers, create a `trapi_identifiers.dhall`:
```haskell
let combine = ./combine.dhall
let variables = ./variables.dhall
in combine.trapi_identifiers variables
```
For ICEES features, create a `icees_api_features.dhall`:
```haskell
let combine = ./combine.dhall
let variables = ./variables.dhall
in combine.icees_features variables
```

## Process for Generating Configuration Files
When deploy a new instance, we can define a selection of feature varibles as follows:
 
 * Create a `variables.dhall` file:
```haskell
let v = ./config/package.dhall
in [
    v.Albuterol,
    v.ReactiveAirwayDx,
    v.CroupDx,
    v.AsthmaDx
]
```

 * Run `dhall-to-yaml`:
```bash
dhall-to-yaml --file pit_mapping.dhall --output pit_mappings.yml
```

## Process for Adding a New ICEES Feature Variable

To add a new ICEES Feature Variable, for example `AvgDailyPM2.5Exposure`
 * add `AvgDailyPM2.5Exposure.dhall` under the appropriate direction, for example, `./config/ChemicalSubstance/AvgDailyPM2.5Exposure.dhall`.
```haskell
{
    name = "AvgDailyPM2.5Exposure",
    mapping = Mapping.EnvironmentalMapping {
        dataset = "cmaq",
        column = "pm2.5",
        statitics = [
            {
                statistic = Avg,
                rename = Suffix "_StudyAvg"
            },
            {
                statistic = Max,
                rename = Suffix "_StudyMax"
            },
            {
                statistic = PrevDate,
                rename = Replace "Avg24hPM2.5Exposure"            
            }
        ]
    },
    binningStrategies = [
        {
            strategy = Cut 5
        },
        {
            strategy = QCut 5,
            suffix = "_qcut"
        }
    ],
    feature = {
        feature_type = ICEESAPIType.Integer {
            minimum = 1,
            maximum = 5
        },
        biolink_types = [
            "biolink:ChemicalSubstance"
        ]
    },
    identifiers = [
        "MESH:D052638"
    ]
}
```
 * Add a field in `./config/package.json`
```haskell
{
  ...
  AvgDailyPM25Exposure = ./ChemicalSubstance/AvgDailyPM2.5Exposure.dhall,
  ...
}
