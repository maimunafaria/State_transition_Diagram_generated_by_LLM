---
source_type: plantuml_rule
source_name: PlantUML Language Reference Guide
source_file: /Users/faria/Downloads/PlantUML_Language_Reference_Guide_en-232-256.pdf
chapter: State Diagram
topics: entry point, exit point, input pin, output pin, expansion, arrow direction
priority: medium
---

# PlantUML State Diagram Points, Pins, and Arrow Direction

Use this document for less common state diagram syntax.

## Entry and exit points

Entry and exit points can be declared with stereotypes.

```plantuml
state e1 <<entryPoint>>
state x1 <<exitPoint>>

[*] --> e1
e1 --> Processing
Processing --> x1
x1 --> [*]
```

## Input and output pins

Use `<<inputPin>>` and `<<outputPin>>` when the diagram needs explicit input/output pin notation.

```plantuml
state input1 <<inputPin>>
state output1 <<outputPin>>

input1 --> Processing
Processing --> output1
```

## Expansion nodes

Use `<<expansionInput>>` and `<<expansionOutput>>` for expansion nodes.

```plantuml
state expIn <<expansionInput>>
state expOut <<expansionOutput>>

expIn --> Processing
Processing --> expOut
```

## Arrow direction

Use directional arrows only when layout control is useful.

```plantuml
State1 -right-> State2
State2 -down-> State3
State3 -left-> State4
State4 -up-> State1
```

Short forms are also allowed.

```plantuml
State1 -r-> State2
State2 -d-> State3
State3 -l-> State4
State4 -u-> State1
```
