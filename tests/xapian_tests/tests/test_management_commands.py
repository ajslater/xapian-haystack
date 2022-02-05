import datetime
import random
from decimal import Decimal
from unittest import TestCase

from django.core.management import call_command

from ..models import BlogEntry
from ..search_indexes import BlogSearchIndex
from .test_backend import HaystackBackendTestCase


class ManagementCommandTestCase(HaystackBackendTestCase, TestCase):
    # fixtures = ["bulk_data"]

    NUM_BLOG_ENTRIES = 1000

    def get_index(self):
        return BlogSearchIndex()

    @staticmethod
    def get_entry(i):
        entry = BlogEntry()
        entry.id = i
        entry.author = "david%s" % i
        entry.url = "http://example.com/%d/" % i
        entry.boolean = bool(i % 2)
        entry.number = i * 5
        entry.float_number = i * 5.0
        entry.decimal_number = Decimal("22.34")
        entry.datetime = datetime.datetime(2009, 2, 25, 1, 1, 1) - datetime.timedelta(
            seconds=i
        )
        entry.date = datetime.date(2009, 2, 23) + datetime.timedelta(days=i)
        return entry

    def setUp(self):
        super().setUp()

        self.sample_objs = []

        for i in range(1, self.NUM_BLOG_ENTRIES + 1):
            entry = self.get_entry(i)
            entry.float_number = random.uniform(0.0, 1000.0)
            self.sample_objs.append(entry)
            entry.save()

        self.backend.update(self.index, BlogEntry.objects.all())

    def verify_indexed_document_count(self, expected):
        count = self.backend.document_count()
        self.assertEqual(count, expected)

    def verify_indexed_documents(self):
        """Confirm that the documents in the search index match the database"""

        count = self.backend.document_count()
        self.assertEqual(count, self.NUM_BLOG_ENTRIES)

        pks = set(BlogEntry.objects.values_list("pk", flat=True))
        doc_ids = set()
        database = self.backend._database()
        for pk in pks:
            xapian_doc = database.get_document(pk)
            doc_id = xapian_doc.get_docid()
            doc_ids.add(doc_id)
        database.close()

        self.assertSetEqual(pks, doc_ids)

    def test_basic_commands(self):
        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("rebuild_index", interactive=False, verbosity=0)
        self.verify_indexed_documents()

    def test_remove(self):
        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

        # Remove several instances.
        BlogEntry.objects.get(pk=1).delete()
        BlogEntry.objects.get(pk=2).delete()
        BlogEntry.objects.get(pk=8).delete()
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # Plain ``update_index`` doesn't fix it.
        call_command("update_index", verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # … but remove does:
        call_command("update_index", remove=True, verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES - 3)

    def test_multiprocessing(self):
        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=2, workers=10, batchsize=10)
        self.verify_indexed_documents()
