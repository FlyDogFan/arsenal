import atexit
import shelve
import cPickle as pickle
from datetime import datetime, timedelta
from copy import deepcopy
from threading import RLock


def timed_cache(seconds=0, minutes=0, hours=0, days=0):

    time_delta = timedelta( seconds=seconds,
                            minutes=minutes,
                            hours=hours,
                            days=days )

    def decorate(f):

        f._lock = RLock()
        f._updates = {}
        f._results = {}

        def do_cache(*args, **kwargs):

            lock = f._lock
            lock.acquire()

            try:
                key = (args, tuple(sorted(kwargs.items(), key=lambda i:i[0])))

                updates = f._updates
                results = f._results

                t = datetime.now()
                updated = updates.get(key, t)

                if key not in results or t-updated > time_delta:
                    # Calculate
                    updates[key] = t
                    result = f(*args, **kwargs)
                    results[key] = deepcopy(result)
                    return result

                else:
                    # Cache
                    return deepcopy(results[key])

            finally:
                lock.release()

        return do_cache

    return decorate

"""
if __name__ == "__main__":

    import time
    class T(object):
        @timed_cache(seconds=2)
        def expensive_func(self, c):
            time.sleep(.2)
            return c

    t = T ()
    for _ in xrange(30):
        time.sleep(.1)
        t1 = time.clock()
        print t.expensive_func('Calling expensive method')
        print "t - %i milliseconds"%int( (time.clock() - t1) * 1000. )
"""

class ShelfBasedCache(object):
    """ cache a function's return value to avoid recalulation and save cache in a shelve. """
    def __init__(self, func, key, None_is_bad=False):
        self.func = func
        self.filename = '{self.func.__name__}.shelf~'.format(self=self)
        self.cache = shelve.open(self.filename, flag='c') #, writeback=True)
        self.key = key
        self.None_is_bad = None_is_bad
        self.__name__ = 'ShelfBasedCache(%s)' % func.__name__
    def __call__(self, *args):
        p_args = self.key(args)
        value = None
        recompute = True
        if self.cache.has_key(p_args):
            recompute = False
            value = self.cache[p_args]
            if value is None and self.None_is_bad:
                recompute = True
        if recompute:
            self.cache[p_args] = value = self.func(*args)
            self.cache.sync()
        return value

def persistent_cache(key=lambda x: x, None_is_bad=False):
    def wrap(f):
        return ShelfBasedCache(f, key, None_is_bad=None_is_bad)
    return wrap


# TODO:
#  * add option to pass a reference to another cache (maybe memcached client)
class memoize(object):
    """ cache a function's return value to avoid recalulation """
    def __init__(self, func):
        self.func = func
        self.cache = {}
        try:
            self.__name__ = func.__name__
            self.__doc__ = func.__doc__
        except AttributeError:
            pass
    def __call__(self, *args):
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            try:
                self.cache[args] = value
            except TypeError:
                # uncachable -- for instance, passing a list as an argument.
                raise TypeError('uncachable arguments %r passed to memoized function.' % (args,))
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            raise TypeError('uncachable arguments %r passed to memoized function.' % (args,))
    def __repr__(self):
        return '<memoize(%r)>' % self.func


## TODO: automatically make a back-up of the pickle
class memoize_persistent(object):
    """
    cache a function's return value to avoid recalulation and save the
    cache (via pickle) at system exit so that it persists.

    WARNING: retrieves cache for functions which might not be equivalent
             if a revision is made to the code which is used to compute it.
    """
    def __init__(self, func, filename=None):
        self.func = func
        self.filename = filename or '{self.func.__name__}.cache.pkl~'.format(self=self)
        self.dirty = False
        self.key = 0
        self.cache = {}
        self.loaded = False
        atexit.register(self.save)

    def save(self):
        if self.cache and self.dirty:
            pickle.dump((self.cache, self.key), file(self.filename,'wb'))
            print '[ATEXIT] saved persistent cache for {self.func.__name__} to file "{self.filename}"'.format(self=self)
        else:
            print "[ATEXIT] found nothing to save in {self.func.__name__}'s cache.".format(self=self)

    def load(self):
        self.loaded = True
        loaded_key = None
        try:
            (cache, loaded_key) = pickle.load(file(self.filename,'r'))
        except IOError:
            pass
        finally:
            if self.key == loaded_key:
                self.cache = cache
                #print 'loaded cache for {self.func.__name__}'.format(self=self)
            else:
                self.cache = {}
                #print 'failed to load cache for {self.func.__name__}'.format(self=self)

    def __call__(self, *args):
        # wait until you call the function to un-pickle
        if not self.loaded:
            self.load()
        try:
            return self.cache[args]
        except KeyError:
            value = self.func(*args)
            try:
                self.cache[args] = value
            except TypeError:
                # uncachable -- for instance, passing a list as an argument.
                raise TypeError('uncachable arguments %r passed to memoized function.' % (args,))
            else:
                self.dirty = True
            return value
        except TypeError:
            # uncachable -- for instance, passing a list as an argument.
            raise TypeError('uncachable arguments %r passed to memoized function.' % (args,))

    def get_cached(self, *args):
        """ If result is cached return it, otherwise return `None`. """
        # wait until you call the function to un-pickle
        if not self.loaded:
            self.load()
        if args in self.cache:
            return self.cache[args]
        else:
            return None
