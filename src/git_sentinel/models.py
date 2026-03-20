"""Typed configuration models for git-sentinel."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HookFailurePolicy(StrEnum):
    CONTINUE = "continue"
    FAIL = "fail"


class CommitSettings(BaseModel):
    """Commit behavior for push-enabled repositories."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    message: str | None = None
    add: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_commit_settings(self) -> CommitSettings:
        if self.enabled:
            if not self.message:
                raise ValueError(
                    "commit.message is required when commit.enabled is true"
                )
            if not self.add:
                raise ValueError(
                    "commit.add must not be empty when commit.enabled is true"
                )
        return self


class RepositoryConfig(BaseModel):
    """Effective repository configuration after defaults are merged."""

    model_config = ConfigDict(extra="forbid")

    name: str
    path: Path
    remote: str = "origin"
    branch: str = "main"
    interval_seconds: int = Field(ge=1, le=86_400)
    pull: bool = True
    push: bool = False
    commit: CommitSettings = Field(default_factory=CommitSettings)
    after_pull: list[list[str]] = Field(default_factory=list)
    after_push: list[list[str]] = Field(default_factory=list)
    hook_failure_policy: HookFailurePolicy = HookFailurePolicy.CONTINUE

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> Path:
        if not isinstance(value, (str, Path)):
            raise TypeError("path must be a string or Path")
        return Path(value).expanduser()

    @model_validator(mode="after")
    def validate_repository(self) -> RepositoryConfig:
        if not self.name.strip():
            raise ValueError("name must not be empty")

        if self.push and not self.commit.enabled:
            raise ValueError(
                "push-enabled repositories require commit.enabled=true "
                "for explicit commit behavior"
            )

        for field_name, commands in (
            ("after_pull", self.after_pull),
            ("after_push", self.after_push),
        ):
            for index, command in enumerate(commands):
                if not command:
                    raise ValueError(f"{field_name}[{index}] must not be empty")
                if any(not part for part in command):
                    raise ValueError(
                        f"{field_name}[{index}] contains an empty command argument"
                    )
        return self


class DefaultsConfig(BaseModel):
    """Top-level defaults applied to repository definitions."""

    model_config = ConfigDict(extra="forbid")

    remote: str = "origin"
    branch: str = "main"
    interval_seconds: int = Field(default=300, ge=1, le=86_400)
    pull: bool = True
    push: bool = False
    commit: CommitSettings = Field(default_factory=CommitSettings)
    after_pull: list[list[str]] = Field(default_factory=list)
    after_push: list[list[str]] = Field(default_factory=list)
    hook_failure_policy: HookFailurePolicy = HookFailurePolicy.CONTINUE


class RawConfig(BaseModel):
    """Raw YAML file model before defaults are merged."""

    model_config = ConfigDict(extra="forbid")

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    repositories: list[dict[str, object]] = Field(min_length=1)


class AppConfig(BaseModel):
    """Application configuration containing fully merged repositories."""

    model_config = ConfigDict(extra="forbid")

    repositories: list[RepositoryConfig]

    @model_validator(mode="after")
    def validate_unique_names(self) -> AppConfig:
        names = [repo.name for repo in self.repositories]
        duplicate_names = {name for name in names if names.count(name) > 1}
        if duplicate_names:
            duplicates = ", ".join(sorted(duplicate_names))
            raise ValueError(
                f"repository names must be unique; duplicates: {duplicates}"
            )
        return self
