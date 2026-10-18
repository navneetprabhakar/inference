"""Canonical records and pinned source evidence."""
from dataclasses import dataclass, field, asdict
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class Source:
    source_id: str
    revision: str
    url: str
    license_id: str
    license_text_sha256: str
    card_sha256: str
    upstream_origins: tuple[str, ...]
    review_status: str = 'sample_only'

    def __post_init__(self):
        object.__setattr__(self, 'upstream_origins', tuple(self.upstream_origins))
        for name, size in [('revision', 40), ('license_text_sha256', 64), ('card_sha256', 64)]:
            if not re.fullmatch(f'[a-f0-9]{{{size}}}', getattr(self, name)):
                raise ValueError(f'Source requires pinned {name}')
        if not all((self.source_id, self.url, self.license_id, self.upstream_origins)):
            raise ValueError('Incomplete source provenance')
        if self.review_status not in ('sample_only', 'training_approved', 'excluded'):
            raise ValueError('Invalid source review status')


@dataclass
class Example:
    example_id: str
    source: str
    source_revision: str
    license_record: str
    parent_group_id: str
    messages: list[dict]
    official_split: str | None = None
    task: str = 'conversation'
    style: str = 'unlabeled'
    content_category: str = 'unreviewed'
    language: str = 'unknown'
    lineage: list[str] = field(default_factory=list)
    upstream_references: list[str] = field(default_factory=list)
    split: str | None = None
    validation_results: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def make_example(source, row_id, group_id, messages, **metadata):
    return Example(example_id=f'{source.source_id}:{row_id}', source=source.source_id,
                   source_revision=source.revision, license_record=digest(asdict(source)),
                   parent_group_id=group_id if group_id.startswith('family:') else f'{source.source_id}:{group_id}', messages=messages,
                   **metadata)
