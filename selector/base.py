import pandas as pd
import numpy as np

import time
import abc

from sklearn.base import TransformerMixin

from robusta.crossval import crossval_score

from ._verbose import _print_last



class Selector(TransformerMixin):


    def transform(self, X):
        """Reduce X to the selected features.

        Parameters
        ----------
        X : DataFrame of shape [n_samples, n_features]
            The input samples.

        Returns
        -------
        Xt : DataFrame of shape [n_samples, n_selected_features]
            The input samples with only the selected features.

        """
        use_cols = self._select_features()
        use_cols = list(use_cols)

        Xt = X[use_cols]
        return Xt


    @abc.abstractmethod
    def _select_features(self):
        """
        Get list of columns to select

        Returns
        -------
        use_cols : list of string, shape (k_features, )
            Columns to selct

        """
        return []



class EmbeddedSelector(Selector):

    def _eval_subset(self, subset, X, y, groups):

        trial = self._find_trial(subset)

        if trial:
            # If subset already evaluated
            score = trial['score']

        else:
            # If subset is completely new
            time_start = time.time()

            self.n_features_ = len(X.columns)

            use_cols = list(subset)
            subset = set(subset)

            scores = crossval_score(self.estimator, self.cv, X[use_cols], y, groups,
                                    scoring=self.scoring, n_jobs=self.n_jobs,
                                    verbose=0)

            # TODO: multimetric case (or check if multimetric)
            score = scores[self.scoring].mean()

            time_end = time.time()

            trial = {
                'subset': subset,
                'score': score,
                'time': time_end-time_start,
            }

        self._append_trial(trial)
        return score


    def _append_trial(self, trial):

        if not hasattr(self, 'trials_'):
            self._reset_trials()

        if trial['score'] >= self.best_score_:
            self.best_iter_ = self.n_iters_
            self.best_score_ = trial['score']
            self.best_subset_ = trial['subset']

        self.trials_ = self.trials_.append(trial, ignore_index=True)

        self.total_time_ = self.trials_['time'].sum()
        self.n_iters_ = self.trials_.shape[0]

        _print_last(self)

        self._check_max_trials()
        self._check_max_time()


    def _reset_trials(self):

        self.trials_ = pd.DataFrame()
        self.best_score_ = -np.inf

        self.total_time_ = .0
        self.n_iters_ = 0


    def _check_max_trials(self):
        if hasattr(self, 'max_iter') and self.max_iter:
            if self.max_iter <= self.n_iters_:
                if self.verbose: print('Iterations limit exceed!')
                raise KeyboardInterrupt


    def _check_max_time(self):
        if hasattr(self, 'max_time') and self.max_time:
            if self.max_time <= self.total_time_:
                if self.verbose: print('Time limit exceed!')
                raise KeyboardInterrupt


    def _find_trial(self, subset):

        if self.n_iters_ == 0:
            return None

        same_subsets = self.trials_['subset'].map(lambda x: _equal_sets(subset, x))

        if same_subsets.any():
            trial = self.trials_[same_subsets].iloc[0]
            return trial.to_dict()
        else:
            return None


def _equal_sets(set1, set2):
    set1, set2 = set(set1), set(set2)
    return len(set1 ^ set2) is 0
