from abc import ABC, abstractmethod


class VideoSource(ABC):

    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def release(self):
        pass