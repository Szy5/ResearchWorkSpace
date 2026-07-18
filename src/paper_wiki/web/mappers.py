from __future__ import annotations

from paper_wiki.assets.models import PaperAssetMeta
from paper_wiki.web.schemas.paper import PaperMetaDTO


def map_paper_meta(meta: PaperAssetMeta) -> PaperMetaDTO:
    return PaperMetaDTO(
        title=meta.title,
        authors=meta.authors,
        abstract=meta.abstract,
        year=meta.year,
        venue=meta.venue,
        arxiv_id=meta.arxiv_id,
        tags=meta.tags,
        contribution_type=meta.contribution_type,
        reviewed=meta.reviewed,
        meta_reviewed=meta.meta_reviewed,
        prior_works_reviewed=meta.prior_works_reviewed,
        added_date=meta.added_date.isoformat(),
        blog_html_path=meta.blog_html_path,
        blog_html_generated_at=meta.blog_html_generated_at,
    )
