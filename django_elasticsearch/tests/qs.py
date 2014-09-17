import mock

from django.test import TestCase
from django.test.utils import override_settings

from django_elasticsearch.managers import es_client
from django_elasticsearch.managers import EsQueryset
from django_elasticsearch.tests.models import TestModel


@override_settings(ELASTICSEARCH_SETTINGS={})
class EsQuerysetTestCase(TestCase):

    def setUp(self):
        # create a bunch of documents
        TestModel.es.create_index(ignore=True)

        self.t1 = TestModel.objects.create(username=u"woot2", first_name=u"John", last_name=u"Smith")
        self.t1.es.do_index()

        self.t2 = TestModel.objects.create(username=u"woot", first_name=u"Jack", last_name=u"Smith")
        self.t2.es.do_index()

        self.t3 = TestModel.objects.create(username=u"BigMama", first_name=u"Mama", last_name=u"Smith")
        self.t3.es.do_index()

        self.t4 = TestModel.objects.create(username=u"foo", first_name=u"Foo", last_name=u"Bar")
        self.t4.es.do_index()

        TestModel.es.do_update()

    def tearDown(self):
        es_client.indices.delete(index=TestModel.es.get_index())

    def test_all(self):
        qs = EsQueryset(TestModel)
        self.assertTrue(self.t1 in qs)
        self.assertTrue(self.t2 in qs)
        self.assertTrue(self.t3 in qs)
        self.assertTrue(self.t4 in qs)

    def test_repr(self):
        qs = EsQueryset(TestModel).order_by('id')
        expected = str(TestModel.objects.all())
        self.assertEqual(expected, str(qs.all()))

    def test_use_cache(self):
        # Note: we use _make_search_body because it's only called
        # if the cache store is not hit
        fake_body = {'query': {'match': {'_all': 'foo'}}}
        with mock.patch.object(EsQueryset,
                               '_make_search_body') as mocked:
            mocked.return_value = fake_body
            qs = EsQueryset(TestModel)
            # eval
            list(qs)
            # use cache
            list(qs)
        mocked.assert_called_once()

        # same for a sliced query
        with mock.patch.object(EsQueryset,
                               '_make_search_body') as mocked:
            mocked.return_value = fake_body
            # re-eval
            list(qs[0:5])
            # use cache
            list(qs[0:5])
        mocked.assert_called_once()

    def test_facets(self):
        qs = EsQueryset(TestModel).facet(['last_name'])
        expected = {
            u'last_name': {
                u'_type': u'terms',
                u'missing': 0,
                u'other': 0,
                u'terms': [{u'count': 3, u'term': u'smith'},
                           {u'count': 1, u'term': u'bar'}],
                u'total': 4
            }
        }
        self.assertEqual(expected, qs.facets)

    def test_non_global_facets(self):
        qs = EsQueryset(TestModel).facet(['last_name'], use_globals=False).query("Foo")
        expected = {
            u'last_name': {
                u'_type': u'terms',
                u'missing': 0,
                u'other': 0,
                u'terms': [{u'count': 1, u'term': u'bar'}],
                u'total': 1
            }
        }
        self.assertEqual(expected, qs.facets)

    def test_suggestions(self):
        qs = EsQueryset(TestModel).query('smath').suggest(['last_name'])
        expected = {
            u'last_name': [
                {u'length': 5,
                 u'offset': 0,
                 u'options': [{u'freq': 3,
                               u'score': 0.8,
                               u'text': u'smith'}],
                 u'text': u'smath'}]}
        self.assertEqual(expected, qs.suggestions)

    def test_count(self):
        self.assertEqual(EsQueryset(TestModel).count(), 4)
        self.assertEqual(EsQueryset(TestModel).query("John").count(), 1)
        self.assertEqual(EsQueryset(TestModel)
                         .filter(last_name=u"Smith")
                         .count(), 3)

    def test_ordering(self):
        qs = EsQueryset(TestModel).order_by('username')
        self.assertTrue(qs[0], self.t3)
        self.assertTrue(qs[1], self.t4)
        self.assertTrue(qs[2], self.t2)
        self.assertTrue(qs[3], self.t1)

    def test_filtering(self):
        qs = EsQueryset(TestModel).filter(last_name=u"Smith")
        self.assertTrue(self.t1 in qs)
        self.assertTrue(self.t2 in qs)
        self.assertTrue(self.t3 in qs)
        self.assertTrue(self.t4 not in qs)

    def test_excluding(self):
        pass
