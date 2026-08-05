import colorsys
import mimetypes
import os
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs
from xml.etree.ElementTree import Element, SubElement

import markdown
import nh3
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from pgvector.django import HnswIndex, VectorField

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Org
from temba.utils import on_transaction_commit
from temba.utils.models import TembaModel, delete_in_batches
from temba.utils.s3 import public_file_storage
from temba.utils.uuid import uuid4


class EscapeRawHTML(Extension):
    """
    Renders raw HTML in the source as visible text instead of markup. The library has no option for this, so the
    documented way to get it is to unregister the two things that recognize HTML in the first place.
    """

    def extendMarkdown(self, md):
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")


# the size and layout an image can be given, carried in the fragment of its URL as #size=small&layout=inline - in the
# markdown itself, so it survives any renderer. Each size is a single pixel cap (small=200, medium=400, large=640)
# that renderers apply as both max-width and max-height, bounding the long axis of any aspect ratio; no fragment means
# full size as a block, which is how markdown renders an image anyway.
IMAGE_SIZES = ("small", "medium", "large")
IMAGE_LAYOUTS = ("block", "inline")
IMAGE_CLASSES = {f"size-{s}" for s in IMAGE_SIZES} | {f"layout-{layout}" for layout in IMAGE_LAYOUTS}


class AnnotateImages(Extension):
    """
    Surfaces the size/layout fragment of each image's URL as classes on its <img> - size-small, layout-inline etc -
    for CSS to act on. The src is left intact, fragment and all; a fragment on an <img> is harmless, and stripping it
    would make the served HTML lie about the markdown it came from.
    """

    def extendMarkdown(self, md):
        md.treeprocessors.register(AnnotateImagesProcessor(md), "annotate_images", 5)


class AnnotateImagesProcessor(Treeprocessor):
    def run(self, root):
        for img in root.iter("img"):
            params = parse_qs(img.get("src", "").partition("#")[2])

            classes = []
            for key, allowed in (("size", IMAGE_SIZES), ("layout", IMAGE_LAYOUTS)):
                value = params.get(key, [""])[0]
                if value in allowed:
                    classes.append(f"{key}-{value}")

            if classes:
                img.set("class", " ".join(classes))


# a cell is one line of markdown - a real newline would end its row - so the editor writes line breaks inside cells
# as literal <br> text, and rendering turns them back into the breaks they mean
CELL_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


class CellBreaks(Extension):
    """
    Turns the literal <br>s inside table cells into the line breaks they mean. Raw HTML is escaped rather than parsed,
    so they arrive as text; a cell is one line of markdown and <br> is the only way it can carry a break. Cells only -
    everywhere else text that merely looks like a tag stays text.
    """

    def extendMarkdown(self, md):
        md.treeprocessors.register(CellBreaksProcessor(md), "cell_breaks", 5)


class CellBreaksProcessor(Treeprocessor):
    def run(self, root):
        for tag in ("th", "td"):
            for cell in root.iter(tag):
                self._reveal(cell)

    def _reveal(self, element):
        # a break can sit inside a cell's emphasis or link as easily as in the cell itself
        for child in list(element):
            self._reveal(child)

        if element.text and CELL_BREAK.search(element.text):
            parts = CELL_BREAK.split(element.text)
            element.text = parts[0]
            for at, part in enumerate(parts[1:]):
                br = Element("br")
                br.tail = part
                element.insert(at, br)

        for child in list(element):
            if child.tail and CELL_BREAK.search(child.tail):
                parts = CELL_BREAK.split(child.tail)
                child.tail = parts[0]
                at = list(element).index(child) + 1
                for offset, part in enumerate(parts[1:]):
                    br = Element("br")
                    br.tail = part
                    element.insert(at + offset, br)


# The column stylesheet a layout table's header cells can carry - `width: 200px; background: #eef2ff` in otherwise
# empty header cells, put there by the editor. Riding in the markdown itself, it survives any renderer; one that
# doesn't understand it just shows it as header text.
COLUMN_DECLARATION = re.compile(r"^(width|background|padding)\s*:\s*(\S+)$", re.IGNORECASE)
COLUMN_WIDTH = re.compile(r"^\d+(px|%)$")
COLUMN_BACKGROUND = re.compile(r"^#[0-9a-f]{3,8}$")
COLUMN_PADDING = re.compile(r"^\d+px$")


def parse_column_style(text: str) -> dict | None:
    """
    Reads a header cell's stylesheet, or returns None when its text isn't one.
    """
    out = {}
    for piece in text.split(";"):
        declaration = piece.strip()
        if not declaration:
            continue
        match = COLUMN_DECLARATION.match(declaration)
        if not match:
            return None
        key, value = match[1].lower(), match[2].lower()
        if key == "width" and not COLUMN_WIDTH.match(value):
            return None
        if key == "background" and not COLUMN_BACKGROUND.match(value):
            return None
        if key == "padding" and not COLUMN_PADDING.match(value):
            return None
        out[key] = value
    return out


def text_on(background: str) -> str:
    """
    A readable text color drawn from a cell's own background: a deep shade of the same hue over a light fill, a
    pale one over a dark fill. Derived the same way the editor derives it, so author and reader see the same text.
    """
    value = background.lstrip("#")
    if len(value) in (3, 4):
        value = "".join(c * 2 for c in value[:3])
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))

    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if l > 0.55:
        s, l = min(s, 0.55), 0.27
    else:
        s, l = min(s, 0.45), 0.95

    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


class ColumnStyles(Extension):
    """
    Realizes the column stylesheets in a layout table's header cells as a colgroup, leaving the header genuinely
    empty. Every header cell has to be empty or read as a stylesheet; any real header text leaves the table alone.
    """

    def extendMarkdown(self, md):
        md.treeprocessors.register(ColumnStylesProcessor(md), "column_styles", 4)


class ColumnStylesProcessor(Treeprocessor):
    def run(self, root):
        for table in root.iter("table"):
            self._decorate(table)

    def _decorate(self, table):
        thead = table.find("thead")
        head = thead.findall(".//th") if thead is not None else []
        if not head:
            return

        styles = []
        for th in head:
            # a header cell with markup in it is real content, however its text reads
            parsed = parse_column_style((th.text or "").strip()) if len(th) == 0 else None
            if parsed is None:
                return
            styles.append(parsed)

        for th in head:
            th.text = ""

        if any(styles):
            colgroup = Element("colgroup")
            for style in styles:
                col = SubElement(colgroup, "col")
                parts = [f"{key}: {style[key]}" for key in ("width", "background") if style.get(key)]
                if parts:
                    col.set("style", "; ".join(parts))
            table.insert(0, colgroup)

        # a sized column only holds its size in a fixed layout, where the unsized columns share what's left
        if any(style.get("width") for style in styles):
            table.set("style", "table-layout: fixed; width: 100%")

        # what belongs to the cells themselves: padding, and text drawn from the column's own color - a colgroup
        # can paint a background but can't reach the text over it. Any alignment the renderer put on a cell stays.
        tbody = table.find("tbody")
        for tr in tbody.findall("tr") if tbody is not None else []:
            for index, td in enumerate(tr.findall("td")):
                style = styles[index] if index < len(styles) else {}
                parts = []
                align = re.search(r"text-align:\s*(left|center|right)", td.get("style") or "")
                if align:
                    parts.append(f"text-align: {align[1]}")
                if style.get("padding"):
                    parts.append(f"padding: {style['padding']}")
                if style.get("background"):
                    parts.append(f"color: {text_on(style['background'])}")
                if parts:
                    td.set("style", "; ".join(parts))
                elif td.get("style"):
                    del td.attrib["style"]


# markdown extensions we render article bodies with. Deliberately conservative - no extension that would make markdown
# itself more expressive than what the editor can round-trip.
MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")

# nh3's default attribute allowances plus class on images (where AnnotateImages puts one) and style on tables and
# their cells and cols (where ColumnStyles and the tables extension put what they realize)
SANITIZE_ATTRIBUTES = {
    **nh3.ALLOWED_ATTRIBUTES,
    "img": nh3.ALLOWED_ATTRIBUTES["img"] | {"class"},
    "col": nh3.ALLOWED_ATTRIBUTES.get("col", set()) | {"style"},
    "table": nh3.ALLOWED_ATTRIBUTES.get("table", set()) | {"style"},
    "td": nh3.ALLOWED_ATTRIBUTES.get("td", set()) | {"style"},
    "th": nh3.ALLOWED_ATTRIBUTES.get("th", set()) | {"style"},
}

# the only declarations a cell's style may carry: the alignment the tables extension writes, and the padding and
# derived text color ColumnStyles writes
CELL_DECLARATION = re.compile(
    r"^(text-align:\s*(left|center|right)|padding:\s*\d+px|color:\s*#[0-9a-f]{3,8})$", re.IGNORECASE
)


def _sanitize_attribute(element: str, attribute: str, value: str) -> str | None:
    """
    Tightens what SANITIZE_ATTRIBUTES lets through: an image's class may only carry the classes AnnotateImages
    emits, and a table, col or cell style only what our own pipeline writes. Nothing else can put those attributes
    there, so like the sanitizing itself this is defense in depth.
    """
    if element == "img" and attribute == "class":
        kept = [c for c in value.split() if c in IMAGE_CLASSES]
        return " ".join(kept) if kept else None
    if element == "col" and attribute == "style":
        return value if parse_column_style(value) else None
    if element == "table" and attribute == "style":
        return value if value == "table-layout: fixed; width: 100%" else None
    if element in ("td", "th") and attribute == "style":
        kept = [d.strip() for d in value.split(";") if d.strip() and CELL_DECLARATION.match(d.strip())]
        return "; ".join(kept) if kept else None
    return value


def render_markdown(body: str) -> str:
    """
    Renders authored markdown for display. Raw HTML is escaped rather than passed through, so that a reader sees what
    the author saw - the editor renders client side and escapes it too, and text that merely looks like a tag (the
    `<url>` of our own quick reply syntax, say) survives instead of being quietly swallowed. Sanitizing stays as
    defense in depth, and still deals with the javascript: URLs markdown will happily make a link out of.
    """
    return nh3.clean(
        markdown.markdown(
            body, extensions=[*MARKDOWN_EXTENSIONS, EscapeRawHTML(), AnnotateImages(), CellBreaks(), ColumnStyles()]
        ),
        attributes=SANITIZE_ATTRIBUTES,
        attribute_filter=_sanitize_attribute,
    )


class Knowledge(TembaModel):
    """
    A source of knowledge that AI agents can search semantically.

    Indexing - crawling, extracting, chunking and embedding - is performed entirely by mailroom, which sweeps for rows
    needing work. This app owns the schema, the CRUD UI and document uploads only; it never calls an embeddings service.
    """

    # authored types - items live in their own Django-owned table, mailroom only reads
    TYPE_SHORTCUTS = "shortcuts"  # the org's shortcuts, read by mailroom straight from tickets_shortcut
    TYPE_HELPDESK = "helpdesk"  # the org's own help articles, read from tickets_article
    # ingested types - items share tickets_knowledgeitem, mailroom owns the lifecycle
    TYPE_WEBSITE = "website"  # a crawled website
    TYPE_DOCUMENTS = "documents"  # uploaded files
    TYPE_CHOICES = (
        (TYPE_SHORTCUTS, _("Shortcuts")),
        (TYPE_HELPDESK, _("Helpdesk")),
        (TYPE_WEBSITE, _("Website")),
        (TYPE_DOCUMENTS, _("Documents")),
    )

    SYSTEM_TYPES = (TYPE_SHORTCUTS, TYPE_HELPDESK)  # one of each per org, created in Org.initialize()
    SYSTEM_NAMES = {TYPE_SHORTCUTS: "Shortcuts", TYPE_HELPDESK: "Helpdesk"}

    STATUS_PENDING = "P"  # needs (re)indexing, mailroom's sweep will pick it up
    STATUS_INDEXING = "I"  # mailroom is working on it
    STATUS_READY = "R"  # indexed and searchable
    STATUS_FAILED = "F"  # last indexing attempt failed, see error
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_INDEXING, _("Indexing")),
        (STATUS_READY, _("Ready")),
        (STATUS_FAILED, _("Failed")),
    )

    REFRESH_NEVER = "never"
    REFRESH_DAILY = "daily"
    REFRESH_WEEKLY = "weekly"
    REFRESH_MONTHLY = "monthly"
    REFRESH_CHOICES = (
        (REFRESH_NEVER, _("Never")),
        (REFRESH_DAILY, _("Daily")),
        (REFRESH_WEEKLY, _("Weekly")),
        (REFRESH_MONTHLY, _("Monthly")),
    )

    # config keys for TYPE_WEBSITE
    CONFIG_URL = "url"
    CONFIG_MAX_DEPTH = "max_depth"
    CONFIG_MAX_PAGES = "max_pages"
    CONFIG_REFRESH = "refresh"

    DEFAULT_MAX_DEPTH = 3
    DEFAULT_MAX_PAGES = 500
    MAX_MAX_PAGES = 5_000
    MAX_URL_LEN = 2048

    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="knowledge")
    knowledge_type = models.CharField(max_length=16, choices=TYPE_CHOICES)

    # type specific settings, e.g. for website: url, max_depth, max_pages, refresh. Empty for other types.
    config = models.JSONField(default=dict)

    # everything below is written by mailroom as it indexes - this app only reads it
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=255, null=True)
    last_indexed_on = models.DateTimeField(null=True)
    num_items = models.IntegerField(default=0)
    num_chunks = models.IntegerField(default=0)

    org_limit_key = Org.LIMIT_KNOWLEDGE

    @classmethod
    def create_system(cls, org):
        """
        Creates the org's two system sources - its shortcut list and its helpdesk.
        """
        assert not org.knowledge.filter(knowledge_type__in=cls.SYSTEM_TYPES).exists(), (
            "org already has system knowledge"
        )

        return [
            org.knowledge.create(
                name=cls.SYSTEM_NAMES[t],
                knowledge_type=t,
                is_system=True,
                created_by=org.created_by,
                modified_by=org.modified_by,
            )
            for t in cls.SYSTEM_TYPES
        ]

    @classmethod
    def create_website(cls, org, user, name: str, url: str, *, max_depth=None, max_pages=None, refresh=None):
        assert cls.is_valid_name(name), f"'{name}' is not a valid knowledge name"
        assert not org.knowledge.filter(name__iexact=name, is_active=True).exists()

        return org.knowledge.create(
            name=name,
            knowledge_type=cls.TYPE_WEBSITE,
            config={
                cls.CONFIG_URL: url,
                cls.CONFIG_MAX_DEPTH: max_depth or cls.DEFAULT_MAX_DEPTH,
                cls.CONFIG_MAX_PAGES: max_pages or cls.DEFAULT_MAX_PAGES,
                cls.CONFIG_REFRESH: refresh or cls.REFRESH_WEEKLY,
            },
            created_by=user,
            modified_by=user,
        )

    @classmethod
    def create_documents(cls, org, user, name: str):
        assert cls.is_valid_name(name), f"'{name}' is not a valid knowledge name"
        assert not org.knowledge.filter(name__iexact=name, is_active=True).exists()

        # nothing to index until files are uploaded
        return org.knowledge.create(
            name=name,
            knowledge_type=cls.TYPE_DOCUMENTS,
            status=cls.STATUS_READY,
            created_by=user,
            modified_by=user,
        )

    @property
    def url(self) -> str:
        return self.config.get(self.CONFIG_URL)

    def mark_pending(self):
        """
        Flags this source as needing (re)indexing so mailroom's sweep picks it up. Called whenever this app changes
        something mailroom's index is derived from - website config, uploaded files.
        """
        self.status = self.STATUS_PENDING
        self.error = None
        self.save(update_fields=("status", "error"))

    def release(self, user):
        assert not (self.is_system and self.org.is_active), "can't release system knowledge"

        # deactivate first so nothing reads or indexes it while we purge
        self.is_active = False
        self.name = self._deleted_name()
        self.num_items = 0
        self.num_chunks = 0
        self.modified_by = user
        self.save(update_fields=("name", "is_active", "num_items", "num_chunks", "modified_by", "modified_on"))

        self._purge()

    def delete(self):
        self._purge()

        super().delete()

    def _purge(self):
        """
        Removes this source's chunks, items, articles and article images. Rows go first; storage objects are only
        removed once their rows are gone.
        """
        # collect storage keys before the rows that name them disappear - two different buckets
        item_paths = list(self.items.exclude(path=None).values_list("path", flat=True))
        image_paths = list(ArticleImage.objects.filter(article__knowledge=self).values_list("path", flat=True))

        delete_in_batches(self.chunks.all())
        delete_in_batches(self.items.all())
        delete_in_batches(ArticleImage.objects.filter(article__knowledge=self))

        # parent is PROTECT so flatten the article tree before deleting it
        self.articles.exclude(parent=None).update(parent=None)
        delete_in_batches(self.articles.all())

        # ATOMIC_REQUESTS means we're inside the request's transaction, so this has to wait for the commit - otherwise
        # a later failure rolls the rows back and leaves them pointing at objects we've already destroyed
        on_transaction_commit(lambda: self._delete_storage(item_paths, image_paths))

    @staticmethod
    def _delete_storage(item_paths: list, image_paths: list):
        for path in item_paths:
            default_storage.delete(path)
        for path in image_paths:
            public_file_storage.delete(path)

    class Meta:
        constraints = [models.UniqueConstraint("org", Lower("name"), name="unique_knowledge_names")]
        indexes = [
            # mailroom's indexing sweep's worklist
            models.Index(name="knowledge_pending", fields=("id",), condition=Q(is_active=True, status="P")),
        ]


class Article(models.Model):
    """
    An article in an org's helpdesk. Written by this app, read by mailroom, which indexes only published, active
    articles.

    Deliberately not a TembaModel: TembaModel.name is capped at 64 chars and NameValidator rejects " and \\, which real
    help titles routinely contain. Soft-deleted like Shortcut so mailroom's delta sweep sees the tombstone - a hard
    delete would leave its chunks stranded until a full reindex.
    """

    STATUS_DRAFT = "D"  # never indexed, never public
    STATUS_PUBLISHED = "P"
    STATUS_CHOICES = ((STATUS_DRAFT, _("Draft")), (STATUS_PUBLISHED, _("Published")))

    MAX_TITLE_LEN = 255
    MAX_SLUG_LEN = 255
    MAX_BODY_LEN = 100_000  # bodies are chunked and embedded, so this bounds what one article can cost to index
    MAX_DEPTH = 2  # total levels - a root and its children, no grandchildren; enforced by the reorder view
    MAX_ARTICLES = 1000  # per helpdesk

    uuid = models.UUIDField(unique=True, default=uuid4)
    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="articles")

    # the tree - a plain self-FK, not mptt (that dep exists only for locations and buys nothing at help-centre depth).
    # Depth is capped at MAX_DEPTH and cycles are rejected server-side.
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, related_name="children")
    sort_order = models.IntegerField(default=0)

    title = models.CharField(max_length=MAX_TITLE_LEN)
    slug = models.SlugField(max_length=MAX_SLUG_LEN)
    body = models.TextField(default="")  # markdown source

    # ISO-639-3, so a helpdesk can hold articles in several languages. Translations aren't linked to each other yet -
    # retrieval doesn't need them, as multilingual-e5 embeds cross-lingually, and linking is a question for the
    # eventual public site rather than for search.
    language = models.CharField(max_length=3, default="eng")

    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_on = models.DateTimeField(null=True)

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_on = models.DateTimeField(default=timezone.now)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    # auto_now is load-bearing: mailroom's staleness sweep is MAX(modified_on) > knowledge.last_indexed_on, so an
    # unpublish or a soft-delete has to bump it for the removal to be noticed
    modified_on = models.DateTimeField(auto_now=True)

    @classmethod
    def create(cls, knowledge, user, title: str, *, body: str = "", parent=None, language: str = None):
        assert knowledge.knowledge_type == Knowledge.TYPE_HELPDESK, "articles can only belong to a helpdesk"
        assert parent is None or parent.knowledge_id == knowledge.id, "parent must be in the same helpdesk"

        # new articles go to the end of their level so creating one never reshuffles the tree
        last = cls.objects.filter(knowledge=knowledge, parent=parent, is_active=True).order_by("-sort_order").first()

        return cls.objects.create(
            knowledge=knowledge,
            parent=parent,
            sort_order=(last.sort_order + 1) if last else 0,
            title=title,
            slug=cls.get_unique_slug(knowledge, title),
            body=body,
            language=language or knowledge.org.flow_languages[0],
            created_by=user,
            modified_by=user,
        )

    @classmethod
    def get_unique_slug(cls, knowledge, title: str, ignore=None) -> str:
        base = slugify(title)[: cls.MAX_SLUG_LEN] or "article"
        qs = cls.objects.filter(knowledge=knowledge, is_active=True)
        if ignore:
            qs = qs.exclude(id=ignore.id)

        slug, count = base, 1
        while qs.filter(slug=slug).exists():
            count += 1
            suffix = f"-{count}"
            slug = f"{base[: cls.MAX_SLUG_LEN - len(suffix)]}{suffix}"

        return slug

    @classmethod
    def get_tree(cls, knowledge) -> list:
        """
        Returns the helpdesk's active articles in display order - depth first, siblings by (sort_order, title) - with
        each one's depth and the uuid of the article it's shown under attached.

        parent_uuid is the parent as rendered rather than as stored, so it's null for an article whose parent has been
        deleted - which is shown as a root here and would otherwise name an article the client can't see. Articles
        stored deeper than MAX_DEPTH allows - data can predate the cap - render flattened rather than hidden: as
        siblings following their parent, under the deepest ancestor the cap does allow.
        """
        active = list(knowledge.articles.filter(is_active=True).order_by("sort_order", "title"))
        active_ids = {a.id for a in active}

        by_parent = defaultdict(list)
        for article in active:
            # an article whose parent isn't in the active set is shown as a root rather than dropped - otherwise it
            # would be invisible here and so unmovable, while still being indexed if it's published
            by_parent[article.parent_id if article.parent_id in active_ids else None].append(article)

        ordered = []

        def visit(article, parent, depth):
            for child in by_parent[article.id if article else None]:
                child.depth = depth
                child.parent_uuid = parent.uuid if parent else None
                ordered.append(child)
                if depth + 1 < cls.MAX_DEPTH:
                    visit(child, child, depth + 1)
                else:
                    # a row at the cap can't be shown with children, so any it has render at its own depth and
                    # parent - flattened into the siblings that follow it rather than dropped
                    visit(child, parent, depth)

        visit(None, None, 0)
        return ordered

    @classmethod
    def apply_sort(cls, knowledge, order: list):
        """
        Applies a new tree ordering given as (uuid, parent uuid or None, sort order) tuples, which need only describe
        what moved. The client's tree is never trusted - the resulting forest is re-derived here and rejected if it
        names an article that isn't in this helpdesk, introduces a cycle, or nests deeper than MAX_DEPTH.
        """
        articles = {str(a.uuid): a for a in knowledge.articles.filter(is_active=True)}
        uuids_by_id = {a.id: uuid for uuid, a in articles.items()}

        # start from the tree as it stands so unmentioned articles keep their place
        parents = {uuid: uuids_by_id.get(a.parent_id) for uuid, a in articles.items()}
        changed = []

        for uuid, parent_uuid, sort_order in order:
            article = articles.get(uuid)
            if not article:
                raise ValueError(f"no such article: {uuid}")
            if parent_uuid is not None and parent_uuid not in articles:
                raise ValueError(f"no such article: {parent_uuid}")

            parents[uuid] = parent_uuid
            article.parent_id = articles[parent_uuid].id if parent_uuid else None
            article.sort_order = sort_order
            changed.append(article)

        for uuid in parents:
            seen, depth, ancestor = {uuid}, 1, parents[uuid]
            while ancestor is not None:
                if ancestor in seen:
                    raise ValueError("articles can't be their own ancestor")
                seen.add(ancestor)
                depth += 1
                if depth > cls.MAX_DEPTH:
                    raise ValueError(f"articles can't be nested more than {cls.MAX_DEPTH} deep")
                ancestor = parents[ancestor]

        # deliberately doesn't touch modified_on: ordering isn't part of what mailroom indexes, so a reorder shouldn't
        # make the helpdesk look stale and re-embed every article in it
        cls.objects.bulk_update(changed, ("parent", "sort_order"))

    @property
    def org(self):
        return self.knowledge.org

    def as_html(self) -> str:
        return render_markdown(self.body)

    def publish(self, user):
        self.status = self.STATUS_PUBLISHED
        self.published_on = timezone.now()
        self.modified_by = user
        self.save(update_fields=("status", "published_on", "modified_by", "modified_on"))

    def unpublish(self, user):
        """
        Reverts to a draft. modified_on bumps, so mailroom's sweep sees the helpdesk as stale and drops our chunks.
        """
        self.status = self.STATUS_DRAFT
        self.published_on = None
        self.modified_by = user
        self.save(update_fields=("status", "published_on", "modified_by", "modified_on"))

    def release(self, user):
        """
        Soft delete - a tombstone, so mailroom's delta sweep notices and drops our chunks. Children are reparented to
        our parent so the tree stays connected, and our images go for good since nothing will render this body again.
        """
        image_paths = list(self.images.values_list("path", flat=True))

        with transaction.atomic():
            self.children.update(parent=self.parent)
            self.images.all().delete()

            self.is_active = False
            self.status = self.STATUS_DRAFT
            self.published_on = None
            self.modified_by = user
            self.save(update_fields=("is_active", "status", "published_on", "modified_by", "modified_on"))

        # ATOMIC_REQUESTS means the atomic block above is only a savepoint, so the storage objects can't go until the
        # request's transaction commits - otherwise a later failure restores the article without its screenshots
        on_transaction_commit(lambda: [public_file_storage.delete(p) for p in image_paths])

    def __str__(self):
        return self.title

    class Meta:
        constraints = [
            models.UniqueConstraint("knowledge", "slug", condition=Q(is_active=True), name="unique_article_slugs")
        ]
        indexes = [
            # the tree, in display order
            models.Index(name="article_by_tree", fields=("knowledge", "parent", "sort_order")),
            # mailroom's staleness + delta sweep
            models.Index(name="article_by_modified", fields=("knowledge", "modified_on")),
        ]


def get_article_image_path(article, image_uuid, content_type: str) -> str:
    # the extension comes from the sniffed content type rather than from the uploaded filename. These objects live in
    # a public, unauthenticated bucket, and storage backends serve a key by the type its extension implies - so a file
    # whose first bytes sniff as an image but which is named ".html" would otherwise be served as HTML from our own
    # domain.
    extension = mimetypes.guess_extension(content_type) or ".bin"

    return (
        f"orgs/{article.knowledge.org_id}/knowledge/{article.knowledge.uuid}/"
        f"articles/{article.uuid}/{image_uuid}{extension}"
    )


class ArticleImage(models.Model):
    """
    A screenshot uploaded to an article and referenced from its markdown by URL. Stored in public storage because the
    eventual standalone help site serves these directly.
    """

    ALLOWED_CONTENT_TYPES = ("image/gif", "image/jpeg", "image/png", "image/webp")
    MAX_UPLOAD_SIZE = 1024 * 1024 * 10  # 10MB
    MAX_IMAGES = 50  # per article

    uuid = models.UUIDField(unique=True, default=uuid4)
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="images")
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=2048)  # key in the public bucket
    content_type = models.CharField(max_length=255)
    size = models.IntegerField()

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def is_allowed_type(cls, content_type: str) -> bool:
        return content_type in cls.ALLOWED_CONTENT_TYPES

    @classmethod
    def from_upload(cls, article, user, file):
        # borrows Media's filename cleaning but not the model itself - its alternates and ffmpeg processing are
        # message attachment concerns that a screenshot has no use for
        from temba.msgs.models import Media

        assert cls.is_allowed_type(file.content_type), "unsupported content type"

        uuid = uuid4()
        name = Media.clean_name(file.name, file.content_type)
        path = public_file_storage.save(get_article_image_path(article, uuid, file.content_type), file)

        return cls.objects.create(
            uuid=uuid,
            article=article,
            name=name,
            path=path,
            content_type=file.content_type,
            size=public_file_storage.size(path),
            created_by=user,
        )

    @property
    def url(self) -> str:
        return public_file_storage.url(self.path)

    def delete(self):
        path = self.path

        super().delete()

        # only remove the storage object once the deletion has committed - see Article.release
        on_transaction_commit(lambda: public_file_storage.delete(path))


def get_knowledge_item_path(knowledge, item_uuid, filename: str) -> str:
    return f"orgs/{knowledge.org_id}/knowledge/{knowledge.uuid}/{item_uuid}{Path(filename).suffix.lower()}"


class KnowledgeItem(models.Model):
    """
    One page or one uploaded document in an ingested knowledge source.

    Writers are split: this app creates document rows on upload (url null, path set); mailroom creates page rows as it
    crawls (url set) and owns status/error/num_chunks for both. A page's uuid is stable across recrawls because rows
    are matched by normalised url within the source - that's what makes incremental reindexing possible, since chunks
    key off that uuid.
    """

    ALLOWED_CONTENT_TYPES = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "text/csv",
        "text/markdown",
        "text/plain",
    )
    MAX_UPLOAD_SIZE = 1024 * 1024 * 20  # 20MB
    MAX_DOCUMENTS = 100  # per documents source

    STATUS_PENDING = "P"
    STATUS_INDEXING = "I"
    STATUS_READY = "R"
    STATUS_FAILED = "F"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_INDEXING, _("Indexing")),
        (STATUS_READY, _("Ready")),
        (STATUS_FAILED, _("Failed")),
    )

    uuid = models.UUIDField(unique=True, default=uuid4)
    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=255)  # page title, or the cleaned original filename

    # null for uploads; the normalised page URL for crawled pages, and their identity within the source
    url = models.URLField(max_length=2048, null=True)

    # storage key: set for uploads (private bucket); optionally the cached extracted text for pages
    path = models.CharField(max_length=2048, null=True)

    content_type = models.CharField(max_length=255)  # mailroom sets text/html for pages
    size = models.IntegerField()  # bytes of the stored/fetched content

    # written by mailroom as it extracts and chunks
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.CharField(max_length=255, null=True)
    num_chunks = models.IntegerField(default=0)

    created_by = models.ForeignKey(  # null for crawled pages - nobody uploaded them
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    created_on = models.DateTimeField(default=timezone.now)

    @classmethod
    def is_allowed_type(cls, content_type: str) -> bool:
        return content_type in cls.ALLOWED_CONTENT_TYPES

    @classmethod
    def clean_name(cls, filename: str) -> str:
        base_name, extension = os.path.splitext(filename)
        base_name = re.sub(r"[^\w\-\[\]\(\) ]", "", base_name).strip()[:200] or "file"
        return base_name + extension[:50]

    @classmethod
    def from_upload(cls, knowledge, user, file):
        assert knowledge.knowledge_type == Knowledge.TYPE_DOCUMENTS, "can only upload to documents knowledge"
        assert cls.is_allowed_type(file.content_type), "unsupported content type"

        uuid = uuid4()
        path = default_storage.save(get_knowledge_item_path(knowledge, uuid, file.name), file)

        obj = cls.objects.create(
            uuid=uuid,
            knowledge=knowledge,
            name=cls.clean_name(file.name),
            url=None,  # explicit: this is what makes it a document rather than a page
            path=path,
            content_type=file.content_type,
            size=default_storage.size(path),
            created_by=user,
        )

        knowledge.mark_pending()
        return obj

    @property
    def org(self):
        return self.knowledge.org

    def delete(self):
        path = self.path

        with transaction.atomic():
            # this item's chunks are no longer valid - mailroom will recompute the source's counters
            delete_in_batches(self.knowledge.chunks.filter(item_key=self.uuid))
            super().delete()
            self.knowledge.mark_pending()

        # only remove the storage object once the deletion has committed - with ATOMIC_REQUESTS the atomic block above
        # is just a savepoint, so this has to wait for the request's transaction
        if path:
            on_transaction_commit(lambda: default_storage.delete(path))

    class Meta:
        constraints = [
            # a page's identity within its source. Postgres treats NULLs as distinct in a unique index, so uploaded
            # documents (url null) are exempt automatically - no partial-index condition needed, and any number of
            # documents can coexist in one source.
            models.UniqueConstraint("knowledge", "url", name="unique_knowledge_item_urls"),
        ]


class KnowledgeChunk(models.Model):
    """
    A chunk of indexed content with its embedding. Rows are written exclusively by mailroom - this app never INSERTs
    or UPDATEs them. It only DELETEs them when the user deletes the owning item or source.
    """

    EMBEDDING_DIMENSIONS = 384  # intfloat/multilingual-e5-small

    knowledge = models.ForeignKey(Knowledge, on_delete=models.PROTECT, related_name="chunks")

    # the owning item's uuid. Not an FK, because the item lives in a different table per source type: KnowledgeItem
    # for pages/documents, Shortcut for shortcuts, Article for helpdesk. One mechanism spanning all four beats an FK
    # plus fallbacks.
    item_key = models.UUIDField()
    item_name = models.CharField(max_length=255)
    item_url = models.URLField(max_length=2048, null=True)

    text = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)

    class Meta:
        indexes = [
            # a single ANN index shared by all orgs and sources - queries filtered by knowledge source rely on
            # pgvector >= 0.8 iterative scans (enforced by migration 0092) to return complete results
            HnswIndex(
                name="knowledgechunk_embedding",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=("vector_cosine_ops",),
            ),
            # lets mailroom replace one item's chunks on reindex, and lets us delete one item's chunks
            models.Index(name="knowledgechunk_by_item", fields=("knowledge", "item_key")),
        ]
