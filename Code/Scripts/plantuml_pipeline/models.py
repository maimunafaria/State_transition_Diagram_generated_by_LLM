from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Case:
    case_id: str
    path: Path
    raw_requirement: str
    structured_requirement: str
    gold_puml: str
    gold_graph: "DiagramGraph"
    gold_validation: "ValidationResult"
    complexity: str


@dataclass
class DiagramGraph:
    states: set[str]
    transitions: list[tuple[str, str, str]]
    initial_targets: list[str]
    final_states: set[str]
    aliases: dict[str, str]
    parse_errors: list[str]
    stereotypes: dict[str, set[str]]
    explicit_states: set[str]
    composite_states: set[str]
    history_states: set[str]

    def transition_set(self) -> set[tuple[str, str, str]]:
        return set(self.transitions)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    initial_state: str | None
    duplicate_transition_count: int
    unreachable_states: list[str]
    state_count: int
    transition_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "initial_state": self.initial_state,
            "duplicate_transition_count": self.duplicate_transition_count,
            "unreachable_states": list(self.unreachable_states),
            "state_count": self.state_count,
            "transition_count": self.transition_count,
        }


@dataclass
class ExperimentConfig:
    run_id: str
    model_group: str
    model_label: str
    model_name: str
    strategy: str
    use_rag: bool
    use_structural_validation: bool
    use_ensemble: bool
    baseline_subset_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_group": self.model_group,
            "model_label": self.model_label,
            "model_name": self.model_name,
            "strategy": self.strategy,
            "use_rag": self.use_rag,
            "use_structural_validation": self.use_structural_validation,
            "use_ensemble": self.use_ensemble,
            "baseline_subset_only": self.baseline_subset_only,
        }
