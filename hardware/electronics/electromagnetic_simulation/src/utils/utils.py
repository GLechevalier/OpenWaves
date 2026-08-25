class TimeSeries(list):
    def __init__(self, time_step, start_time = 0.0):
        super().__init__()
        self.time_step = time_step
        self.start_time = start_time

    def get(self, time):
        """
        Docstring for get
        This function allows the user to get the time series at a specific time. 
        It also comes built in with a feature to get the time series at a time between time steps (since it's continuous)

        :param time: Description
        The time where you want to get the time series at
        """
        i = int(time//self.time_step)
        r = time%self.time_step
        if r==0:
            return self[i]
        else:
            if time>self.time_step*len(self) or time<self.start_time:
                raise ValueError(time)
            else:
                return (1-r)*self[i] + r*self[i+1]
    
    def get_time_list(self):
        return [float(self.start_time + i*self.time_step) for i in range(len(self))]

    def to_dict(self):
        return {"values" : self, "time": self.get_time_list()}
        


if __name__ == "__main__":
    ts = TimeSeries(time_step=0.1)
    for i in range(10):
        ts.append(2*i)
    print(ts)
    print(ts.get(0.3))
    print(ts.to_dict())