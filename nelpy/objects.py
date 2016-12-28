import warnings
import numpy as np
# from shapely.geometry import Point

class EpochArray:
    """An array of epochs, where each epoch has a start and stop time.

    Parameters
    ----------
    samples : np.array
        If shape (n_epochs, 1) or (n_epochs,), the start time for each epoch.
        If shape (n_epochs, 2), the start and stop times for each epoch.
    fs : float, optional
        Sampling rate in Hz. If fs is passed as a parameter, then time is assumed to 
        be in sample numbers instead of actual time.
    duration : np.array, float, or None, optional
        The length of the epoch. If (float) then the same duration is assumed for every epoch.
    meta : dict, optional
        Metadata associated with spiketrain.

    Attributes
    ----------
    time : np.array
        The start and stop times for each epoch. With shape (n_epochs, 2).
    samples : np.array
        The start and stop samples for each epoch. With shape (n_epochs, 2).
    fs: float
        Sampling frequency (Hz).
    meta : dict
        Metadata associated with spiketrain.

    """

    def __init__(self, samples, fs=None, duration=None, meta=None):

        # if no samples were received, return an empty EpochArray:
        if len(samples) == 0:
            self.samples = np.array([])
            self.time = np.array([])
            self._fs = None
            self._meta = None
            return

        samples = np.squeeze(samples)

        # TODO: what exactly does this do? In which case is this useful? I mean, the zero dim thing?
        if samples.ndim == 0:
            samples = samples[..., np.newaxis]

        if samples.ndim > 2:
            raise ValueError("samples must be a 1D or a 2D vector")

        if fs is not None:
            try:
                if fs <= 0:
                    raise ValueError("sampling rate must be positive")
            except:
                # why is this raised when above ValueError is raised as well?
                raise TypeError("sampling rate must be a scalar")

        if duration is not None:
            duration = np.squeeze(duration).astype(float)
            if duration.ndim == 0:
                duration = duration[..., np.newaxis]

            if samples.ndim == 2 and duration.ndim == 1:
                raise ValueError(
                    "duration not allowed when using start and stop times")

            if len(duration) > 1:
                if samples.ndim == 1 and samples.shape[0] != duration.shape[0]:
                    raise ValueError(
                        "must have same number of time and duration samples")

            if samples.ndim == 1 and duration.ndim == 1:
                stop_epoch = samples + duration
                samples = np.hstack(
                    (samples[..., np.newaxis], stop_epoch[..., np.newaxis]))

        if samples.ndim == 1 and duration is None:
            samples = samples[..., np.newaxis]

        if samples.ndim == 2 and samples.shape[1] != 2:
            samples = np.hstack(
                (samples[0][..., np.newaxis], samples[1][..., np.newaxis]))

        if samples[:, 0].shape[0] != samples[:, 1].shape[0]:
            raise ValueError(
                "must have the same number of start and stop times")

        # TODO: what if start == stop? what will this break? This situation can arise
        # automatically when slicing a spike train with one or no spikes, for example
        # in which case the automatically inferred support is a delta dirac
        if samples.ndim == 2 and np.any(samples[:, 1] - samples[:, 0] < 0):
            raise ValueError("start must be less than or equal to stop")

        # TODO: why not just sort in-place here? Why store sort_idx? Why do we explicitly sort epoch samples, but not spike times?
        sort_idx = np.argsort(samples[:, 0])
        samples = samples[sort_idx]

        # TODO: already checked this; try tp refactor
        if fs is not None:
            self.samples = samples
            self.time = samples / fs
        else:
            self.samples = samples
            self.time = self.samples

        self._fs = fs
        self._meta = meta

    def __repr__(self):
        if self.isempty:
            return "<empty EpochArray>"
        if self.n_epochs > 1:
            nstr = "%s epochs" % (self.n_epochs)
        else:
            nstr = "1 epoch"
        dstr = "totaling %s seconds" % self.duration
        return "<EpochArray: %s> %s" % (nstr, dstr)

    def __getitem__(self, idx):
        # TODO: add support for slices, ints, and EpochArrays

        if isinstance(idx, EpochArray):
            if idx.isempty:
                return EpochArray([])
            if idx.fs != self.fs:
                epoch = self.intersect(epoch=EpochArray(idx.time * self.fs, fs=self.fs), boundaries=True)
            else:
                epoch = self.intersect(epoch=idx, boundaries=True) # what if fs of slicing epoch is different?
            if epoch.isempty:
                return EpochArray([])
            return epoch
        elif isinstance(idx, int):
            try:
                epoch = EpochArray(
                    np.array([self.samples[idx,:]]), fs=self.fs, meta=self.meta)
                return epoch
            except: # index is out of bounds, so return an empty spiketrain
                return EpochArray([])
        elif isinstance(idx, slice):
            start = idx.start
            if start is None:
                start = 0
            if start >= self.n_epochs:
                return EpochArray([])
            stop = idx.stop
            if stop is None:
                stop = -1
            else:
                stop = np.min(np.array([stop - 1, self.n_epochs - 1]))
            return EpochArray(np.array(
                [self.samples[start:stop+1,:]]), fs=self.fs, meta=self.meta)
        else:
            raise TypeError(
                'unsupported subsctipting type {}'.format(type(idx)))

        return EpochArray([self.starts[idx], self.stops[idx]])

    @property
    def meta(self):
        """Meta data associated with SpikeTrain."""
        if self._meta is None:
            warnings.warn("meta data is not available")
        return self._meta

    @meta.setter
    def meta(self, val):
        self._meta = val

    @property
    def fs(self):
        """(float) Sampling frequency."""
        if self._fs is None:
            warnings.warn("No sampling frequency has been specified!")
        return self._fs

    @fs.setter
    def fs(self, val):
        try:
            if val <= 0:
                pass
        except:
            raise TypeError("sampling rate must be a scalar")
        if val <= 0:
            raise ValueError("sampling rate must be positive")

        if self._fs != val:
            warnings.warn(
                "Sampling frequency has been updated! This will modify the spike times.")
        self._fs = val
        self.time = self.samples / val

    @property
    def centers(self):
        """(np.array) The center of each epoch."""
        if self.isempty:
            return []
        return np.mean(self.time, axis=1)

    @property
    def durations(self):
        """(np.array) The duration of each epoch."""
        if self.isempty:
            return 0
        return self.time[:, 1] - self.time[:, 0]

    @property
    def duration(self):
        """(float) The total duration of the epoch array."""
        if self.isempty:
            return 0
        return np.array(self.time[:, 1] - self.time[:, 0]).sum()

    @property
    def starts(self):
        """(np.array) The start of each epoch."""
        if self.isempty:
            return []
        return self.time[:, 0]

    @property
    def _sampleStarts(self):
        """(np.array) The start of each epoch, in samples"""
        if self.isempty:
            return []
        return self.samples[:, 0]

    @property
    def start(self):
        """(np.array) The start of the first epoch."""
        if self.isempty:
            return []
        return self.time[:, 0][0]

    @property
    def _sampleStart(self):
        """(np.array) The start of the first epoch, in samples"""
        if self.isempty:
            return []
        return self.samples[:, 0][0]

    @property
    def stops(self):
        """(np.array) The stop of each epoch."""
        if self.isempty:
            return []
        return self.time[:, 1]

    @property
    def _sampleStops(self):
        """(np.array) The stop of each epoch, in samples"""
        if self.isempty:
            return []
        return self.samples[:, 1]

    @property
    def stop(self):
        """(np.array) The stop of the last epoch."""
        if self.isempty:
            return []
        return self.time[:, 1][-1]

    @property
    def _sampleStop(self):
        """(np.array) The stop of the first epoch, in samples"""
        return self.samples[:, 0][0]

    @property
    def n_epochs(self):
        """(int) The number of epochs."""
        if self.isempty:
            return 0
        return len(self.time[:, 0])

    @property
    def isempty(self):
        """(bool) Empty SpikeTrain."""
        if len(self.time) == 0:
            empty = True
        else:
            empty = False
        return empty

    def copy(self):
        """(EpochArray) Returns a copy of the current epoch array."""
        new_starts = np.array(self._sampleStarts)
        new_stops = np.array(self._sampleStops)
        return EpochArray(new_starts, duration=new_stops - new_starts, fs=self.fs, meta=self.meta)

    def intersect(self, epoch, boundaries=True, meta=None):
        """Finds intersection (overlap) between two sets of epoch arrays. Sampling rates can be different.
        Parameters
        ----------
        epoch : nelpy.EpochArray
        boundaries : bool
            If True, limits start, stop to epoch start and stop.
        meta : dict, optional
            New dictionary of meta data for epoch ontersection.
        Returns
        -------
        intersect_epochs : nelpy.EpochArray
        """
        if self.isempty or epoch.isempty:
            warnings.warn('epoch intersection is empty')
            return EpochArray([], duration=[], meta=meta)

        new_starts = []
        new_stops = []
        epoch_a = self.copy().merge()
        epoch_b = epoch.copy().merge()

        for aa in epoch_a.time:
            for bb in epoch_b.time:
                if (aa[0] <= bb[0] < aa[1]) and (aa[0] < bb[1] <= aa[1]):
                    new_starts.append(bb[0])
                    new_stops.append(bb[1])
                elif (aa[0] < bb[0] < aa[1]) and (aa[0] < bb[1] > aa[1]):
                    new_starts.append(bb[0])
                    if boundaries:
                        new_stops.append(aa[1])
                    else:
                        new_stops.append(bb[1])
                elif (aa[0] > bb[0] < aa[1]) and (aa[0] < bb[1] < aa[1]):
                    if boundaries:
                        new_starts.append(aa[0])
                    else:
                        new_starts.append(bb[0])
                    new_stops.append(bb[1])
                elif (aa[0] >= bb[0] < aa[1]) and (aa[0] < bb[1] >= aa[1]):
                    if boundaries:
                        new_starts.append(aa[0])
                        new_stops.append(aa[1])
                    else:
                        new_starts.append(bb[0])
                        new_stops.append(bb[1])

        if not boundaries:
            new_starts = np.unique(new_starts)
            new_stops = np.unique(new_stops)

        if self.fs != epoch.fs:
            warnings.warn(
                'sampling rates are different; intersecting along time only and throwing away fs')
            return EpochArray(np.hstack([np.array(new_starts)[..., np.newaxis],
                                         np.array(new_stops)[..., np.newaxis]]), fs=None, meta=meta)
        elif self.fs is None:
            return EpochArray(np.hstack([np.array(new_starts)[..., np.newaxis],
                                         np.array(new_stops)[..., np.newaxis]]), fs=None, meta=meta)
        else:
            return EpochArray(np.hstack([np.array(new_starts)[..., np.newaxis],
                                         np.array(new_stops)[..., np.newaxis]]) * self.fs, fs=self.fs, meta=meta)

    def merge(self, gap=0.0):
        """Merges epochs that are close or overlapping.
        Parameters
        ----------
        gap : float, optional
            Amount (in time) to consider epochs close enough to merge.
            Defaults to 0.0 (no gap).
        Returns
        -------
        merged_epochs : nelpy.EpochArray
        """
        if self.isempty:
            return self

        if gap < 0:
            raise ValueError("gap cannot be negative")

        epoch = self.copy()

        if self.fs is not None:
            gap = gap * self.fs

        stops = epoch._sampleStops[:-1] + gap
        starts = epoch._sampleStarts[1:]
        to_merge = (stops - starts) >= 0

        new_starts = [epoch._sampleStarts[0]]
        new_stops = []

        next_stop = epoch._sampleStops[0]
        for i in range(epoch.time.shape[0] - 1):
            this_stop = epoch._sampleStops[i]
            next_stop = max(next_stop, this_stop)
            if not to_merge[i]:
                new_stops.append(next_stop)
                new_starts.append(epoch._sampleStarts[i + 1])

        new_stops.append(epoch._sampleStops[-1])

        new_starts = np.array(new_starts)
        new_stops = np.array(new_stops)

        return EpochArray(new_starts, duration=new_stops - new_starts, fs=self.fs, meta=self.meta)

    def expand(self, amount, direction='both'):
        """Expands epoch by the given amount.
        Parameters
        ----------
        amount : float
            Amount (in time) to expand each epoch.
        direction : str
            Can be 'both', 'start', or 'stop'. This specifies
            which direction to resize epoch.
        Returns
        -------
        expanded_epochs : nelpy.EpochArray
        """
        if direction == 'both':
            resize_starts = self.time[:, 0] - amount
            resize_stops = self.time[:, 1] + amount
        elif direction == 'start':
            resize_starts = self.time[:, 0] - amount
            resize_stops = self.time[:, 1]
        elif direction == 'stop':
            resize_starts = self.time[:, 0]
            resize_stops = self.time[:, 1] + amount
        else:
            raise ValueError("direction must be 'both', 'start', or 'stop'")

        return EpochArray(np.hstack((resize_starts[..., np.newaxis],
                                     resize_stops[..., np.newaxis])))

    def shrink(self, amount, direction='both'):
        """Shrinks epoch by the given amount.
        Parameters
        ----------
        amount : float
            Amount (in time) to shrink each epoch.
        direction : str
            Can be 'both', 'start', or 'stop'. This specifies
            which direction to resize epoch.
        Returns
        -------
        shrinked_epochs : nelpy.EpochArray
        """
        both_limit = min(self.durations / 2)
        if amount > both_limit and direction == 'both':
            raise ValueError("shrink amount too large")

        single_limit = min(self.durations)
        if amount > single_limit and direction != 'both':
            raise ValueError("shrink amount too large")

        return self.expand(-amount, direction)

    def join(self, epoch, meta=None):
        """Combines [and merges] two sets of epochs. Epochs can have different sampling rates.
        Parameters
        ----------
        epoch : nelpy.EpochArray
        meta : dict, optional
            New meta data dictionary describing the joined epochs.
        Returns
        -------
        joined_epochs : nelpy.EpochArray
        """

        if self.isempty:
            return epoch
        if epoch.isempty:
            return self

        if self.fs != epoch.fs:
            warnings.warn(
                'sampling rates are different; joining along time only and throwing away fs')
            join_starts = np.concatenate((self.time[:, 0], epoch.time[:, 0]))
            join_stops = np.concatenate((self.time[:, 1], epoch.time[:, 1]))
            #TODO: calling merge() just once misses some instances. 
            # I haven't looked carefully enough to know which edge cases these are... 
            # merge() should therefore be checked!
            # return EpochArray(join_starts, fs=None, duration=join_stops - join_starts, meta=meta).merge().merge()
            return EpochArray(join_starts, fs=None, duration=join_stops - join_starts, meta=meta)
        else:
            join_starts = np.concatenate(
                (self.samples[:, 0], epoch.samples[:, 0]))
            join_stops = np.concatenate(
                (self.samples[:, 1], epoch.samples[:, 1]))

        # return EpochArray(join_starts, fs=self.fs, duration=join_stops - join_starts, meta=meta).merge().merge()
        return EpochArray(join_starts, fs=self.fs, duration=join_stops - join_starts, meta=meta)

        def contains(self, value):
        """Checks whether value is in any epoch.

        Parameters
        ----------
        epochs: nelpy.EpochArray
        value: float or int

        Returns
        -------
        boolean

        """
        # TODO: consider vectorizing this loop, which should increase speed, but also greatly increase memory?
        # alternatively, if we could assume something about epochs being sorted, this can also be made much faster than the current O(N)
        for start, stop in zip(self.starts, self.stops):
            if start <= value <= stop:
                return True
        return False


class SpikeTrain:
    """A set of spike times associated with an individual putative neuron.

    Parameters
    ----------
    samples : np.array(dtype=np.float64)
    fs : float, optional
        Sampling rate in Hz. If fs is passed as a parameter, then time is assumed to 
        be in sample numbers instead of actual time.
    support : EpochArray, optional
        EpochArray array on which spiketrain is defined. Default is [0, last spike] inclusive.
    label : str or None, optional
        Information pertaining to the source of the spiketrain.
    cell_type : str or other, optional
        Identified cell type indicator, e.g., 'pyr', 'int'.
    meta : dict
        Metadata associated with spiketrain.

    Attributes
    ----------
    time : np.array(dtype=np.float64)
        With shape (n_samples,). Always in seconds.
    samples : np.array(dtype=np.float64)
        With shape (n_samples,). Sample numbers corresponding to spike times, if available.
    support : EpochArray on which spiketrain is defined.
    n_spikes: integer
        Number of spikes in SpikeTrain.
    fs: float
        Sampling frequency (Hz).
    cell_type : str or other
        Identified cell type.
    label : str or None
        Information pertaining to the source of the spiketrain.
    meta : dict
        Metadata associated with spiketrain.
    """

    def __init__(self, samples, fs=None, support=None, label=None, cell_type=None, meta=None):
        samples = np.squeeze(samples)

        if samples.shape == (): #TODO: doesn't this mean it's empty?
            samples = samples[..., np.newaxis]

        if samples.ndim != 1:
            raise ValueError("samples must be a vector")

        if fs is not None:
            try:
                if fs <= 0:
                    raise ValueError("sampling rate must be positive")
            except:
                # why is this raised when above ValueError is raised as well?
                raise TypeError("sampling rate must be a scalar")

        if label is not None and not isinstance(label, str):
            raise ValueError("label must be a string")

        if fs is not None:
            time = samples / fs
        else:
            time = samples

        if len(samples) > 0:
            if support is None:
                self.support = EpochArray(np.array([0, samples[-1]]), fs=fs)
            else:
                # restrict spikes to only those within the spiketrain's
                # support:
                self.support = support
                indices = []
                for eptime in self.support.time:
                    t_start = eptime[0]
                    t_stop = eptime[1]
                    indices.append((time >= t_start) & (time <= t_stop))
                indices = np.any(np.column_stack(indices), axis=1)
                if np.count_nonzero(indices) < len(samples):
                    warnings.warn(
                        'ignoring spikes outside of spiketrain support')
                samples = samples[indices]
                time = time[indices]
        else: #TODO: we could have handled this earlier, right?
            self.support = EpochArray([])
            self.time = np.array([])

        self.samples = samples
        self.time = time

        self._fs = fs
        self.label = label
        self._cell_type = cell_type
        self._meta = meta

    def __repr__(self):
        if self.isempty:
            return "<empty SpikeTrain>"
        if self.fs is not None:
            fsstr = " at %s Hz" % self.fs
        else:
            fsstr = ""
        if self.label is not None:
            labelstr = " from %s" % self.label
        else:
            labelstr = ""
        if self.cell_type is not None:
            typestr = "[%s]" % self.cell_type
        else:
            typestr = ""

        return "<SpikeTrain%s: %s spikes%s>%s" % (typestr, self.n_spikes, fsstr, labelstr)

    def __getitem__(self, idx):
        if isinstance(idx, EpochArray):
            if idx.isempty:
                return SpikeTrain([])
            epoch = self.support.intersect(idx, boundaries=True)
            if epoch.isempty:
                return SpikeTrain([])
            indices = []
            for eptime in epoch.time:
                t_start = eptime[0]
                t_stop = eptime[1]
                indices.append((self.time >= t_start) & (self.time <= t_stop))
            indices = np.any(np.column_stack(indices), axis=1)
            return SpikeTrain(self.samples[indices],
                              fs=self.fs,
                              support=epoch,
                              label=self.label,
                              cell_type=self.cell_type,
                              meta=self.meta)
        elif isinstance(idx, int):
            try:
                epoch = EpochArray(
                    np.array([self.samples[idx], self.samples[idx]]), fs=self.fs, meta=self.meta)
            except: # index is out of bounds, so return an empty spiketrain
                epoch = EpochArray([])
                return SpikeTrain([], support=epoch)
            return SpikeTrain(self.samples[idx],
                              fs=self.fs,
                              support=epoch,
                              label=self.label,
                              cell_type=self.cell_type,
                              meta=self.meta)
        elif isinstance(idx, slice):
            start = idx.start
            if start is None:
                start = 0
            if start >= self.n_spikes:
                return SpikeTrain([],
                                  fs=self.fs,
                                  support=None,
                                  label=self.label,
                                  cell_type=self.cell_type,
                                  meta=self.meta)
            stop = idx.stop
            if stop is None:
                stop = -1
            else:
                stop = np.min(np.array([stop - 1, self.n_spikes - 1]))
            epoch = EpochArray(np.array(
                [self.samples[start], self.samples[stop]]), fs=self.fs, meta=self.meta)
            return SpikeTrain(self.samples[idx],
                              fs=self.fs,
                              support=epoch,
                              label=self.label,
                              cell_type=self.cell_type,
                              meta=self.meta)
        else:
            raise TypeError(
                'unsupported subsctipting type {}'.format(type(idx)))

    @property
    def n_spikes(self):
        """(int) The number of spikes."""
        return len(self.time)

    @property
    def isempty(self):
        """(bool) Empty SpikeTrain."""
        if len(self.time) == 0:
            empty = True
        else:
            empty = False
        return empty

    @property
    def issorted(self):
        """(bool) Sorted SpikeTrain."""

        from itertools import tee

        def pairwise(iterable):
            a, b = tee(iterable)
            next(b, None)
            return zip(a, b)

        def is_sorted(iterable, key=lambda a, b: a <= b):
            return all(key(a, b) for a, b in pairwise(iterable))

        return is_sorted(self.samples)

    @property
    def cell_type(self):
        """The neuron cell type."""
        if self._cell_type is None:
            warnings.warn("Cell type has not yet been specified!")
        return self._cell_type

    @cell_type.setter
    def cell_type(self, val):
        self._cell_type = val

    @property
    def meta(self):
        """Meta information associated with SpikeTrain."""
        if self._meta is None:
            warnings.warn("meta data is not available")
        return self._meta

    @meta.setter
    def meta(self, val):
        self._meta = val

    @property
    def fs(self):
        """(float) Sampling frequency."""
        if self._fs is None:
            warnings.warn("No sampling frequency has been specified!")
        return self._fs

    @fs.setter
    def fs(self, val):
        try:
            if val <= 0:
                pass
        except:
            raise TypeError("sampling rate must be a scalar")
        if val <= 0:
            raise ValueError("sampling rate must be positive")

        if self._fs != val:
            warnings.warn(
                "Sampling frequency has been updated! This will modify the spike times.")
        self._fs = val
        self.time = self.samples / val

    def time_slice(self, t_start, t_stop):
        """Creates a new nelpy.SpikeTrain corresponding to the time slice of
        the original between (and including) times t_start and t_stop. Setting
        either parameter to None uses infinite endpoints for the time interval.

        Parameters
        ----------
        spikes : nelpy.SpikeTrain
        t_start : float
        t_stop : float

        Returns
        -------
        sliced_spikes : nelpy.SpikeTrain
        """
        if t_start is None:
            t_start = -np.inf
        if t_stop is None:
            t_stop = np.inf

        if t_start > t_stop:
            raise ValueError("t_start cannot be greater than t_stop")

        indices = (self.time >= t_start) & (self.time <= t_stop)

        return self[indices]

    def time_slices(self, t_starts, t_stops):
        """Creates a new object corresponding to the time slice of
        the original between (and including) times t_start and t_stop. Setting
        either parameter to None uses infinite endpoints for the time interval.

        Parameters
        ----------
        spiketrain : nelpy.SpikeTrain
        t_starts : list of floats
        t_stops : list of floats

        Returns
        -------
        sliced_spiketrain : nelpy.SpikeTrain
        """

        # todo: check if any stops are before starts, like in EpochArray class
        if len(t_starts) != len(t_stops):
            raise ValueError("must have same number of start and stop times")

        indices = []
        for t_start, t_stop in zip(t_starts, t_stops):
            indices.append((self.time >= t_start) & (self.time <= t_stop))
        indices = np.any(np.column_stack(indices), axis=1)

        return self[indices]

    def shift(self, time_offset, fs=None):
        """Creates a new object corresponding to the original spike train, but
        shifted by time_offset (can be positive or negative).

        Parameters
        ----------
        spiketrain : nelpy.SpikeTrain
        time_offset : float
            Time offset, either in actual time (default) or in sample numbers if fs is specified.
        fs : float, optional
            Sampling frequency.

        Returns
        -------
        spiketrain : nelpy.SpikeTrain
        """
        warnings.warn("SpikeTrain.shift() has not been implemented yet!")
