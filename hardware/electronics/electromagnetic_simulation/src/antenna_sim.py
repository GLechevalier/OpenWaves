# -*- coding: utf-8 -*-
"""
 Simple Patch Antenna Tutorial

 Tested with
  - python 3.10
  - openEMS v0.0.34+

 (c) 2015-2023 Thorsten Liebig <thorsten.liebig@gmx.de>

"""
### Import Libraries
import os
import sys
import tempfile
from pylab import *

from CSXCAD  import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import *

from matplotlib.animation import FuncAnimation, FFMpegWriter
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MicrostripPatchAntenna:
    def __init__(self, FDTD, CSX, patch_width, patch_length, patch_thickness, delta_x, feed_length, feed_width=0.1, feed_R=50):
        self.FDTD = FDTD
        self.CSX = CSX
        self.patch_width=patch_width
        self.patch_length = patch_length
        self.patch_thickness = patch_thickness
        self.delta_x = delta_x
        self.feed_R = feed_R
        self.feed_length=feed_length
        self.feed_width = feed_width
        return
    
    def create_antenna(self, x=0, y=0, z=0, quarter_wave_transformer=True, patch=None):
        patch_width = self.patch_width
        patch_length = self.patch_length
        patch_thickness = self.patch_thickness
        feed_width = self.feed_width

        if not patch:
            patch = self.CSX.AddMetal('patch') # create a perfect electric conductor (PEC)

        start4 = [-patch_width/2+x, -patch_length/2+y, z]
        stop4 = [patch_width/2+x, patch_length/2+y, z + patch_thickness]
        patch.AddBox(priority=10, start=start4, stop=stop4)
        
        if quarter_wave_transformer:
            q_w_t_length = 0.723
        else:
            q_w_t_length=0
        quarter_wave_transformer_width = 0.09
        start = [-q_w_t_length-patch_width/2+x, -quarter_wave_transformer_width/2+y, z]
        stop = [-patch_width/2+x, quarter_wave_transformer_width/2+y, z+ patch_thickness]
        patch.AddBox(priority=10, start=start, stop=stop)
        
        start = [-self.feed_length-q_w_t_length-patch_width/2+x, -self.feed_width/2+y, z]
        stop = [-q_w_t_length-patch_width/2+x, feed_width/2+y, z+ patch_thickness]
        patch.AddBox(priority=10, start=start, stop=stop)
        
        self.patch = patch
        
        return self

class  SeriesFedMicrostripPatchArray:
    def __init__(
            self, 
            FDTD, 
            CSX, 
            patch_width, 
            patch_length, 
            patch_thickness, 
            delta_x, 
            delta_y, 
            feed_length=2.498, 
            feed_width=0.28, 
            q_w_t_width=0.1,
            q_w_t_length=0.3,
            interpatch_length=2.498, 
            substrate_thickness=0.127, 
            feed_R=50,
            inter_feed_width=0.1,
        ):
        self.FDTD = FDTD
        self.CSX = CSX
        self.patch_width=patch_width
        self.patch_length = patch_length
        self.patch_thickness = patch_thickness
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.interpatch_length = interpatch_length
        self.inter_feed_length = interpatch_length - patch_width + delta_x
        self.feed_length = feed_length
        self.feed_width = feed_width
        self.q_w_t_width=q_w_t_width
        self.q_w_t_length = q_w_t_length
        self.feed_R = feed_R
        self.inter_feed_width=inter_feed_width
        
        self.substrate_thickness = substrate_thickness
        return
    
    def create_antenna(self, x=0, y=0, z=0,quarter_wave_transformer=False, patch=None, name="patch"):
        patch_width = self.patch_width
        patch_length = self.patch_length
        patch_thickness = self.patch_thickness
        delta_x = self.delta_x
        delta_y = self.delta_y
        length = self.feed_length
        feed_width = self.feed_width
        inter_feed_width = self.inter_feed_width
        inter_feed_length = self.inter_feed_length

        if not patch:
            patch = self.CSX.AddMetal(name) # create a perfect electric conductor (PEC)
        start = [patch_width/2+inter_feed_length+ x, -patch_length/2 + y, z]
        stop  = [3*patch_width/2 +inter_feed_length-delta_x + x , patch_length/2 + y, z+patch_thickness]
        patch.AddBox(priority=10, start=start, stop=stop) # add a box-primitive to the metal property 'patch'
        
        start1 = [patch_width/2+inter_feed_length-delta_x+x, -patch_length/2+y, z]
        stop1 = [patch_width/2+inter_feed_length +x , -inter_feed_width/2-delta_y+y, z+patch_thickness]
        patch.AddBox(priority=10, start=start1, stop=stop1)

        start2 = [patch_width/2+inter_feed_length-delta_x+x, inter_feed_width/2+delta_y+y, z]
        stop2 = [patch_width/2+inter_feed_length+x, patch_length/2+y, z+patch_thickness]
        patch.AddBox(priority=10, start=start2, stop=stop2)

        # Connector between microstrip patch antenna and the patch antenna
        start3 = [patch_width/2+ x, -inter_feed_width/2+y, z]
        stop3 = [patch_width/2+inter_feed_length+x, inter_feed_width/2 +y, z+patch_thickness]
        patch.AddBox(priority=10, start=start3, stop=stop3)

        start4 = [-patch_width/2+x, -patch_length/2+y, z]
        stop4 = [patch_width/2+x, patch_length/2+y, z + patch_thickness]
        patch.AddBox(priority=10, start=start4, stop=stop4)

        # Add the feedline
        if quarter_wave_transformer:
            q_w_t_length = 0.723
        else:
            q_w_t_length=0
        
        quarter_wave_transformer_width = 0.1
        start = [-q_w_t_length-patch_width/2+x, -quarter_wave_transformer_width/2+y, z]
        stop = [-patch_width/2+x, quarter_wave_transformer_width/2+y, z+ patch_thickness]
        patch.AddBox(priority=10, start=start, stop=stop)

        
        # start = [-length-q_w_t_length-patch_width/2+x, -self.feed_width/2+y, z]
        # stop = [-q_w_t_length-patch_width/2+x, feed_width/2+y, z+ patch_thickness]
        # patch.AddBox(priority=10, start=start, stop=stop)

        self.patch = patch

        return self

    def create_quarter_wave_transformer(self, patch, x_offset, y_offset, theta):

        q_w_t_width = self.q_w_t_width
        q_w_t_length = self.q_w_t_length

        v_x_outer = [- q_w_t_width / 2,  - q_w_t_width / 2]
        v_y_outer = [-q_w_t_length, 0]
        v_x_inner = [q_w_t_width / 2, q_w_t_width / 2]
        v_y_inner = [0, - q_w_t_length]

        x_h = np.array(v_x_outer + v_x_inner)
        y_h = np.array(v_y_outer + v_y_inner)

        x_h, y_h = self.rotate(x=x_h, y=y_h, theta=theta)
        x_h, y_h = self.translate(x=x_h, y=y_h, x_translate=x_offset,y_translate=y_offset)

        patch.AddLinPoly(
            points=[x_h, y_h],
            norm_dir='z',
            elevation=self.substrate_thickness,
            length=self.patch_thickness
        )
        return
    
    def rotate(self, x, y, theta):
        XY = np.vstack([x,y])
        rot = np.array([[np.cos(theta), -np.sin(theta)],[np.sin(theta), np.cos(theta)]])
        XY = np.transpose(np.transpose(XY) @ rot)

        x_r = XY[0,:]
        y_r = XY[1,:]
        return x_r,y_r
    
    def translate(self, x,y, x_translate=0, y_translate=0):
        return x+x_translate, y+y_translate
    
    def offset_polyline(self, points, dist):
        """Offset polyline to the LEFT of travel direction by dist."""
        n = len(points)
        result = np.zeros_like(points)
        for i in range(n):
            if i == 0:
                t = points[1] - points[0]
            elif i == n - 1:
                t = points[-1] - points[-2]
            else:
                t = points[i + 1] - points[i - 1]
            norm = np.linalg.norm(t)
            if norm < 1e-12:
                result[i] = points[i]
                continue
            t = t / norm
            normal = np.array([-t[1], t[0]])
            result[i] = points[i] + dist * normal
        return result

    def make_outline(self, points, fw=0.20):
        """Create closed polygon outline (left edge forward, right edge backward)."""
        left = self.offset_polyline(points, fw / 2)
        right = self.offset_polyline(points, -fw / 2)
        x = np.concatenate([left[:, 0], right[::-1, 0]])
        y = np.concatenate([left[:, 1], right[::-1, 1]])
        return x, y

    def create_port(self, end_coords, id:int, orientation:str, excite:float=0.0, feed_width=None):
        """
        Docstring for create_port
        
        :param self: Description
        :param end_coords: Description
        :param id: Description
        :param orientation: Description
        Can only be 'y' or 'x'
        :param excite: Description
        """
        start = end_coords[:]
        stop = end_coords[:]

        if feed_width is None:
            feed_width = self.feed_width

        if orientation == 'y':
            start[1] += -feed_width
        else:
            start[0] += -feed_width
        stop[2] = self.substrate_thickness

        self.port = self.FDTD.AddLumpedPort(id, self.feed_R, start, stop, 'z', excite, priority=5, edges2grid='xy')
        return

class BlackWavesRadarRX(SeriesFedMicrostripPatchArray):
    def __init__(
            self, 
            FDTD, 
            CSX, 
            patch_width, 
            patch_length, 
            patch_thickness, 
            delta_x, 
            delta_y, 
            feed_length=2.498, 
            feed_width=0.28, 
            q_w_t_width=0.1,
            q_w_t_length=0.3,
            interpatch_length=2.498, 
            substrate_thickness=0.127, 
            feed_R=50,
            inter_feed_width=0.1, 
            spacing_x=2.498, 
            spacing_y=2.498
        ):
        super().__init__(
            FDTD=FDTD, 
            CSX=CSX, 
            patch_width=patch_width, 
            patch_length=patch_length, 
            patch_thickness=patch_thickness, 
            delta_x=delta_x, 
            delta_y=delta_y, 
            feed_length=feed_length, 
            feed_width=feed_width, 
            q_w_t_width=q_w_t_width,
            q_w_t_length=q_w_t_length,
            feed_R=feed_R,
            interpatch_length=interpatch_length,
            inter_feed_width=inter_feed_width,
            substrate_thickness=substrate_thickness
        )
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y
        return

    def create_antenna(self, x=0, y=0, z=0,quarter_wave_transformer=False, patch=None, id=1):
        
        self.RX1 = SeriesFedMicrostripPatchArray(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width
        ).create_antenna(name="RX1",x=x-self.spacing_x,y=y+self.spacing_y,z=z,quarter_wave_transformer=quarter_wave_transformer, patch=patch)
        
        self.RX2 = SeriesFedMicrostripPatchArray(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width
        ).create_antenna(name="RX2", x=x,y=y,z=z,quarter_wave_transformer=quarter_wave_transformer, patch=patch)
        
        self.RX3 = SeriesFedMicrostripPatchArray(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width
        ).create_antenna(name="RX3",x=x-self.spacing_x,y=y-self.spacing_y,z=z,quarter_wave_transformer=quarter_wave_transformer, patch=patch)
        
        self.create_feedline_RX1(patch=self.RX1.patch, x=x-self.spacing_x,y=y+self.spacing_y, theta=np.pi/2, id=2*(id-1)+1)
        self.create_feedline_RX2(patch=self.RX2.patch, x=x,y=y, theta=np.pi/2, id=2*(id-1)+2)
        self.create_feedline_RX3(patch=self.RX3.patch, x=x-self.spacing_x,y=y-self.spacing_y, theta=np.pi/2, id=2*(id-1)+3)
        
        return self

    def create_feedline_RX1(
            self, 
            patch, 
            x=0,
            y=0, 
            theta=0, 
            id=0,
            excite=0.0,
            long_feedline=False
        ):
        x_offset = x-self.patch_width/2
        y_offset = y
        fw = 0.2

        self.create_quarter_wave_transformer(patch=patch, x_offset=x_offset, y_offset=y_offset, theta=theta)

        if long_feedline:
            path = SerpentinePath(start_x=0.0, start_y=-0.3, start_heading=270.0)
            path.add_straight(2.11)
            path.add_arc(radius=0.58, sweep_deg=47, turn='L')
            path.add_straight(0.53)
            path.add_arc(radius=0.5, sweep_deg=47, turn='R')
            path.add_straight(0.1)
            path.add_arc(radius=0.5, sweep_deg=85, turn='R')
            path.add_straight(0.24)
            path.add_arc(radius=0.6, sweep_deg=85, turn='L')
            path.add_straight(0.39)
            path.add_arc(radius=0.5, sweep_deg=90, turn='L')
            path.add_straight(0.72)
            path.add_arc(radius=0.7, sweep_deg=70, turn='R')
            path.add_straight(0.4)
            path.add_arc(radius=0.1, sweep_deg=20, turn='R')

            x_coords, y_coords = path.make_feedline(fw=fw)
            x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
            x_coords, y_coords = self.translate(x_coords, y_coords, x_offset, y_offset)

            patch.AddLinPoly(
                points=[x_coords, y_coords],
                norm_dir='z',
                elevation=self.substrate_thickness,
                length=self.patch_thickness
            )

            end_coords = [x_coords[len(x_coords)//2], y_coords[len(x_coords)//2], 0]
        else:
            end_coords =  [
                x_offset - self.q_w_t_length,
                y_offset+0.3 - self.q_w_t_width/2, 
                0
            ]

        self.RX1.create_port(
            end_coords=end_coords,
            id=id,
            feed_width= self.q_w_t_width,
            orientation='y',
            excite=excite
        )

        return

    def create_feedline_RX2(self, patch, x=0,y=0, theta=0, id = 0, excite=0.0, long_feedline=False):
        x_offset = x-self.patch_width/2
        y_offset = y
        fw = 0.2

        self.create_quarter_wave_transformer(patch=patch, x_offset=x_offset, y_offset=y_offset, theta=theta)

        if long_feedline:
            path = SerpentinePath(start_x=0.0, start_y=-0.3, start_heading=270.0)
            path.add_straight(8.7)              # Vertical down

            x_coords, y_coords = path.make_feedline(fw=fw)
            x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
            x_coords, y_coords = self.translate(x_coords, y_coords, x_offset, y_offset)

            patch.AddLinPoly(
                points=[x_coords, y_coords],
                norm_dir='z',
                elevation=self.substrate_thickness,
                length=self.patch_thickness
            )

            end_coords = [x_coords[len(x_coords)//2], y_coords[len(x_coords)//2], 0]
        else : 
            end_coords =  [
                x_offset - self.q_w_t_length,
                y_offset+0.3 - self.q_w_t_width/2, 
                0
            ]
        self.RX2.create_port(
            end_coords=end_coords,
            id=id,
            feed_width=self.q_w_t_width,
            orientation='y',
            excite=excite
        )
        return

    def create_feedline_RX3(self, patch, x=0,y=0, theta=0, id=0, excite=0.0, long_feedline=False):
        x_offset = x-self.patch_width/2
        y_offset = y
        fw = 0.2

        self.create_quarter_wave_transformer(patch=patch, x_offset=x_offset, y_offset=y_offset, theta=theta)

        if long_feedline:
            path = SerpentinePath(start_x=0.0, start_y=-0.3, start_heading=270.0)
            path.add_straight(2.11)
            path.add_arc(radius=0.58, sweep_deg=47, turn='R')
            path.add_straight(0.53)
            path.add_arc(radius=0.5, sweep_deg=47, turn='L')
            path.add_straight(0.1)
            path.add_arc(radius=0.5, sweep_deg=85, turn='L')
            path.add_straight(0.24)
            path.add_arc(radius=0.6, sweep_deg=85, turn='R')
            path.add_straight(0.39)
            path.add_arc(radius=0.5, sweep_deg=90, turn='R')
            path.add_straight(0.72)
            path.add_arc(radius=0.7, sweep_deg=70, turn='L')
            path.add_straight(0.4)
            path.add_arc(radius=0.1, sweep_deg=20, turn='L')


            x_coords, y_coords = path.make_feedline(fw=fw)
            x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
            x_coords, y_coords = self.translate(x_coords, y_coords, x_offset, y_offset)

            patch.AddLinPoly(
                points=[x_coords, y_coords],
                norm_dir='z',
                elevation=self.substrate_thickness,
                length=self.patch_thickness
            )

            end_coords = [x_coords[len(x_coords)//2], y_coords[len(x_coords)//2], 0]
        else:
            end_coords =  [
                x_offset - self.q_w_t_length,
                y_offset+0.3 - self.q_w_t_width/2, 
                0
            ]

        self.RX3.create_port(
            end_coords=end_coords,
            id=id,
            feed_width=self.q_w_t_width,
            orientation='y',
            excite=excite
        )
        return

class BlackWavesRadarTX(SeriesFedMicrostripPatchArray):
    def __init__(
            self, 
            FDTD, 
            CSX, 
            patch_width, 
            patch_length, 
            patch_thickness, 
            delta_x, 
            delta_y, 
            feed_length=2.498, 
            feed_width=0.28, 
            q_w_t_width=0.1,
            q_w_t_length=0.3,
            interpatch_length=2.498, 
            substrate_thickness=0.127, 
            feed_R=50,
            inter_feed_width=0.1, 
            spacing_x=2.498, 
            spacing_y=2.498,
            antennas_to_excite = {
                "TX1":1,
                "TX2":0
            }
        ):
        super().__init__(
            FDTD=FDTD, 
            CSX=CSX, 
            patch_width=patch_width, 
            patch_length=patch_length, 
            patch_thickness=patch_thickness, 
            delta_x=delta_x, 
            delta_y=delta_y, 
            feed_length=feed_length, 
            feed_width=feed_width, 
            q_w_t_width=q_w_t_width,
            q_w_t_length=q_w_t_length,
            interpatch_length=interpatch_length,
            feed_R=feed_R,
            inter_feed_width=inter_feed_width,
            substrate_thickness=substrate_thickness,
            
        )
        self.spacing_x = spacing_x
        self.spacing_y = spacing_y
        self.antennas_to_excite = antennas_to_excite
        
        return

    def create_antenna(self, x=0, y=0, z=0, quarter_wave_transformer=False, patch=None, id=1):
        
        self.TX1 = SeriesFedMicrostripPatchArray(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=0, #self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width
        ).create_antenna(
            name="TX1",
            x=x,
            y=y+self.spacing_y/2,
            z=z, 
            quarter_wave_transformer=quarter_wave_transformer, 
            patch=patch,
            )
        
        self.TX2 = SeriesFedMicrostripPatchArray(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=0, #self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width
        ).create_antenna(
            name="TX2",
            x=x,
            y=y-self.spacing_y/2,
            z=z, 
            quarter_wave_transformer=quarter_wave_transformer, 
            patch=patch,
            )

        self.create_feedline_TX1(patch=self.TX1.patch,x=x,y=y+self.spacing_y/2,theta=np.pi/2, id=2*(id-1)+1,excite=float(self.antennas_to_excite["TX1"]))
        self.create_feedline_TX2(patch=self.TX2.patch,x=x,y=y-self.spacing_y/2,theta=np.pi/2, id=2*(id-1)+2,excite=float(self.antennas_to_excite["TX2"]))

        return self

    def create_feedline_TX1(self, patch, x=0,y=0, theta=0, id=0, excite=0.0, long_feedline=False):
        x_offset = x - self.patch_width/2 
        y_offset = y
        fw = 0.2

        self.create_quarter_wave_transformer(patch=patch, x_offset=x_offset, y_offset=y_offset, theta=theta)
        
        if long_feedline:
            path = SerpentinePath(start_x=0.0, start_y=0.0, start_heading=270.0)
            path.add_straight(1.62)          # 1
            path.add_arc(0.50, 45.0, 'R')   # 2
            path.add_straight(0.48)          # 3
            path.add_arc(0.40, 45.0, 'L')   # 4
            path.add_straight(0.15)          # 5
            path.add_arc(0.40, 90.0, 'L')   # 6
            path.add_straight(0.36)          # 7
            path.add_arc(0.50, 90.0, 'R')   # 8
            path.add_straight(0.12)          # 9
            path.add_arc(0.80, 41.54, 'R')  # 10
            path.add_arc(2.00, 46.20, 'R')  # 11
            path.add_arc(1.00, 47.26, 'R')  # 12
            path.add_straight(0.93)          # 13
            path.add_arc(0.50, 45.0, 'L')   # 14
            path.add_straight(1.23)          # 15
            path.add_arc(0.50, 41.7, 'L')   # 16
            path.add_straight(1.36)          # 17
            path.add_arc(0.50, 41.7, 'R')   # 18
            path.add_straight(0.71)          # 19
            
            x_coords, y_coords = path.make_feedline(fw=fw)
            x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
            x_coords, y_coords = self.translate(x_coords, y_coords, -3.59, y)

            patch.AddLinPoly(
                points=[x_coords, y_coords],
                norm_dir='z',
                elevation=self.substrate_thickness,
                length=self.patch_thickness
            )
            end_coords = [x_coords[len(x_coords)//2], y_coords[len(x_coords)//2], 0]
            orientation = 'x'
        else:
            end_coords =  [
                x_offset - self.q_w_t_length,
                y_offset+0.3 - self.q_w_t_width/2, 
                0
            ]
            orientation = 'y'
        
        self.TX1.create_port(
            end_coords=end_coords,
            id=id,
            feed_width=self.q_w_t_width,
            orientation=orientation,
            excite=excite
        )

        return
    
    def create_feedline_TX2(self, patch, x=0, y=0, theta=0, id=0, excite=0.0, long_feedline=False):
        x_offset = x - self.patch_width / 2
        y_offset = y
        fw = 0.2

        self.create_quarter_wave_transformer(patch=patch, x_offset=x_offset, y_offset=y_offset, theta=theta)

        if long_feedline:
            path = SerpentinePath(start_x=0.0, start_y=-0.3, start_heading=270.0)
            path.add_straight(2.11)              # Vertical down
            path.add_arc(3.84, 90.0, 'R')       # R3.84, 90° right turn (down -> left)
            path.add_straight(4.90)              # Horizontal left

            x_coords, y_coords = path.make_feedline(fw=fw)
            x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
            x_coords, y_coords = self.translate(x_coords, y_coords, x_offset, y_offset)

            patch.AddLinPoly(
                points=[x_coords, y_coords],
                norm_dir='z',
                elevation=self.substrate_thickness,
                length=self.patch_thickness
            )
            end_coords = [x_coords[len(x_coords)//2], y_coords[len(x_coords)//2], 0]
            orientation = 'x'
        else:
            end_coords =  [
                x_offset - self.q_w_t_length,
                y_offset+0.3 - self.q_w_t_width/2, 
                0
            ]
            orientation = 'y'

        self.TX2.create_port(
            end_coords=end_coords,
            id=id,
            feed_width=self.q_w_t_width,
            orientation=orientation,
            excite=excite
        )
        return
    
    
class SerpentinePath:
    def __init__(self, start_x=0.0, start_y=0.0, start_heading=270.0, arc_pts=32):
        self.cx = start_x
        self.cy = start_y
        self.heading = start_heading
        self.arc_pts = arc_pts
        self.points = []

    def add_straight(self, length):
        dx = length * np.cos(np.deg2rad(self.heading))
        dy = length * np.sin(np.deg2rad(self.heading))
        self.points.append((self.cx, self.cy))
        self.cx += dx
        self.cy += dy
        self.points.append((self.cx, self.cy))

    def hard_turn(self, angle, turn):
        if turn == 'R':
            self.heading = (self.heading - angle) % 360
        else:
            self.heading = (self.heading + angle) % 360
        return

    def add_arc(self, radius, sweep_deg, turn):
        """turn: 'R' = right/CW (heading decreases), 'L' = left/CCW (heading increases)"""
        if turn == 'R':
            center_angle = self.heading - 90.0
            angle_start = self.heading + 90.0
            angle_end = angle_start - sweep_deg
        else:
            center_angle = self.heading + 90.0
            angle_start = self.heading - 90.0
            angle_end = angle_start + sweep_deg

        ccx = self.cx + radius * np.cos(np.deg2rad(center_angle))
        ccy = self.cy + radius * np.sin(np.deg2rad(center_angle))

        angles = np.linspace(np.deg2rad(angle_start), np.deg2rad(angle_end), self.arc_pts)
        for a in angles:
            self.points.append((ccx + radius * np.cos(a), ccy + radius * np.sin(a)))

        self.cx = ccx + radius * np.cos(np.deg2rad(angle_end))
        self.cy = ccy + radius * np.sin(np.deg2rad(angle_end))

        if turn == 'R':
            self.heading = (self.heading - sweep_deg) % 360
        else:
            self.heading = (self.heading + sweep_deg) % 360

    def get_points(self):
        pts = np.array(self.points)
        if len(pts) < 2:
            return pts
        mask = np.ones(len(pts), dtype=bool)
        for i in range(1, len(pts)):
            if np.linalg.norm(pts[i] - pts[i - 1]) < 1e-10:
                mask[i] = False
        return pts[mask]
    
    def offset_polyline(self, points, dist):
        """Offset polyline to the LEFT of travel direction by dist."""
        n = len(points)
        result = np.zeros_like(points)
        for i in range(n):
            if i == 0:
                t = points[1] - points[0]
            elif i == n - 1:
                t = points[-1] - points[-2]
            else:
                t = points[i + 1] - points[i - 1]
            norm = np.linalg.norm(t)
            if norm < 1e-12:
                result[i] = points[i]
                continue
            t = t / norm
            normal = np.array([-t[1], t[0]])
            result[i] = points[i] + dist * normal
        return result

    def make_outline(self, points, fw=0.20):
        """Create closed polygon outline (left edge forward, right edge backward)."""
        left = self.offset_polyline(points, fw / 2)
        right = self.offset_polyline(points, -fw / 2)
        x = np.concatenate([left[:, 0], right[::-1, 0]])
        y = np.concatenate([left[:, 1], right[::-1, 1]])
        return x, y

    def make_feedline(self, fw):
        pts = self.get_points()
        x_coords, y_coords = self.make_outline(pts, fw)
        return x_coords, y_coords

    def plot_verification(self):
        fw = 0.20
        pts = self.get_points()
        ox, oy = self.make_outline(pts, fw)

        fig, axes = plt.subplots(2, 2, figsize=(16, 14))

        # Full centerline
        ax = axes[0, 0]
        ax.plot(pts[:, 0], pts[:, 1], 'b-', lw=1.5)
        ax.plot(pts[0, 0], pts[0, 1], 'go', ms=8, label='Start')
        ax.plot(pts[-1, 0], pts[-1, 1], 'rs', ms=8, label='End')
        ax.set_aspect('equal'); ax.grid(True, alpha=0.3); ax.legend()
        ax.set_title('Full Centerline')

        # Full outline
        ax = axes[0, 1]
        ax.fill(ox, oy, alpha=0.5, color='steelblue')
        ax.plot(ox, oy, 'b-', lw=0.5)
        ax.plot(pts[:, 0], pts[:, 1], 'k--', lw=0.3, alpha=0.5)
        ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
        ax.set_title(f'Full Feedline (w={fw}mm)')

        # Zoom: S-curve + top (segs 1-9)
        ax = axes[1, 0]
        ax.fill(ox, oy, alpha=0.4, color='steelblue')
        ax.plot(ox, oy, 'b-', lw=0.5)
        ax.plot(pts[:, 0], pts[:, 1], 'k--', lw=0.5)
        ax.set_xlim(-2.5, 0.5); ax.set_ylim(-4.5, 0.5)
        ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
        ax.set_title('Zoom: S-curve (segs 1-9)')

        # Zoom: U-turn (segs 9-13)
        ax = axes[1, 1]
        ax.fill(ox, oy, alpha=0.4, color='steelblue')
        ax.plot(ox, oy, 'b-', lw=0.5)
        ax.plot(pts[:, 0], pts[:, 1], 'k--', lw=0.5)
        ax.set_xlim(-5.5, -1.0); ax.set_ylim(-6.0, -3.0)
        ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
        ax.set_title('Zoom: U-turn (segs 9-13)')

        for ax in axes.flat:
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)')

        plt.tight_layout()
        plt.show()


class BlackWavesRadar(BlackWavesRadarRX, BlackWavesRadarTX):
    def __init__(
            self, 
            FDTD,
            CSX, 
            patch_width, 
            patch_length, 
            patch_thickness, 
            delta_x, 
            delta_y, 
            feed_length=2.498,
            feed_width=0.2,
            q_w_t_width=0.1,
            q_w_t_length=0.3,
            interpatch_length=2.498, 
            substrate_thickness=0.127, 
            feed_R=50,
            inter_feed_width=0.1,
            spacing_x=2.498, 
            spacing_y=2.498, 
            rx_tx_spacing_x=11.8, 
            rx_tx_spacing_y=5.3,
            antennas_to_excite={
                "TX1":1,
                "TX2":0
            }):
        
        super().__init__(
            FDTD=FDTD, 
            CSX=CSX, 
            patch_width=patch_width, 
            patch_length=patch_length, 
            patch_thickness=patch_thickness, 
            delta_x=delta_x, 
            delta_y=delta_y, 
            feed_length=feed_length, 
            feed_width=feed_width, 
            q_w_t_width=q_w_t_width,
            q_w_t_length=q_w_t_length,
            feed_R=feed_R,
            interpatch_length=interpatch_length,
            inter_feed_width=inter_feed_width,
            substrate_thickness=substrate_thickness,
            spacing_x=spacing_x,
            spacing_y=spacing_y
        )
        self.rx_tx_spacing_x = rx_tx_spacing_x
        self.rx_tx_spacing_y = rx_tx_spacing_y
        self.antennas_to_excite = antennas_to_excite
    
    def create_antenna(self, x=0, y=0, z=0, quarter_wave_transformer=True, patch=None): 
        y_offset = 2.5

        self.TX = BlackWavesRadarTX(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width,
            spacing_x=self.spacing_x,
            spacing_y=self.spacing_y,
            antennas_to_excite = self.antennas_to_excite
        ).create_antenna(x-self.rx_tx_spacing_y/2, y-self.rx_tx_spacing_x/2+y_offset, z, quarter_wave_transformer, patch, id=1)

        self.RX = BlackWavesRadarRX(
            FDTD=self.FDTD,
            CSX=self.CSX,
            patch_width=self.patch_width,
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width=self.q_w_t_width,
            q_w_t_length=self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            substrate_thickness=self.substrate_thickness,
            feed_R=self.feed_R,
            inter_feed_width=self.inter_feed_width,
            spacing_x=self.spacing_x,
            spacing_y=self.spacing_y
        ).create_antenna(x+self.rx_tx_spacing_y/2, y+self.rx_tx_spacing_x/2+y_offset, z, quarter_wave_transformer, patch,id=2)
        
        self.ports = {
            "RX" : {
                "RX1":self.RX.RX1.port,
                "RX2":self.RX.RX2.port,
                "RX3":self.RX.RX3.port,
            },
            "TX" : {
                "TX1":self.TX.TX1.port,
                "TX2":self.TX.TX2.port,
            }
        }
        
        #anti_coupler = self.CSX.AddMetal('anti_coupler_1')
        #self.create_gnd_patch(x=x,y=y,patch=anti_coupler, theta=np.pi/2)
        return self
    
    def create_gnd_patch(self, x,y,patch, theta=0):
        path = SerpentinePath(start_x=0.0, start_y=0.0, start_heading=0.0)
        path.add_straight(5.40)
        path.hard_turn(angle=90, turn='L')
        path.add_straight(1.35)
        path.add_arc(radius=0.85, sweep_deg=85, turn='R')
        path.add_straight(0.24)
        path.add_arc(radius=0.25, sweep_deg=85, turn='L')
        path.add_straight(0.1)
        path.add_arc(radius=0.25, sweep_deg=47, turn='L')
        path.add_straight(0.53)
        path.add_arc(radius=0.83, sweep_deg=47, turn='R')
        path.add_straight(0.63)
        path.hard_turn(angle=45, turn='L')
        path.add_straight(0.14)
        path.hard_turn(angle=45, turn='L')
        path.add_straight(1.47)
        path.hard_turn(angle=45, turn='R')
        path.add_straight(0.86)
        path.hard_turn(angle=45, turn='R')
        path.add_straight(6.18)
        path.hard_turn(angle=45, turn='R')
        path.add_straight(3.79)
        path.hard_turn(angle=45, turn='R')
        path.add_straight(4.50)
        path.hard_turn(angle=45, turn='R')
        path.add_straight(3.65)
        path.hard_turn(angle=45, turn='L')
        path.add_straight(0.1)
        path.hard_turn(angle=90, turn='R')
        path.add_straight(6.89)
        path.hard_turn(angle=90, turn='R')
        path.add_straight(2.08)
        path.hard_turn(angle=45, turn='L')
        path.add_straight(0.14)
        path.hard_turn(angle=45, turn='L')
        path.add_straight(0.63)
        path.add_arc(radius=0.83, sweep_deg=47, turn='R')
        path.add_straight(0.53)
        path.add_arc(radius=0.25, sweep_deg=47, turn='L')
        path.add_straight(0.1)
        path.add_arc(radius=0.25, sweep_deg=85, turn='L')
        path.add_straight(0.24)
        path.add_arc(radius=0.85, sweep_deg=85, turn='R')
        path.add_straight(0.39)
        path.add_arc(radius=0.75, sweep_deg=90, turn='R')
        path.add_straight(0.72)
        path.add_arc(radius=0.45, sweep_deg=70, turn='L')
        path.add_straight(0.03)
        path.add_arc(radius=0.20, sweep_deg=110, turn='L')
        path.add_straight(2.66)
        path.hard_turn(angle=90, turn='R')
        path.add_straight(1.38)
        path.hard_turn(angle=90, turn='L')
        path.add_straight(0.71)
        path.add_arc(radius=0.25, sweep_deg=41.7, turn='L')
        path.add_straight(1.36)
        path.add_arc(radius=0.75, sweep_deg=41.7, turn='R')
        path.add_straight(1.23)
        path.add_arc(radius=0.75, sweep_deg=45, turn='R')
        path.add_straight(0.93)
        path.add_arc(radius=0.75, sweep_deg=47.26, turn='L')
        path.add_arc(radius=1.75, sweep_deg=46.2, turn='L')
        path.add_arc(radius=0.55, sweep_deg=41.54, turn='L')
        path.add_straight(0.12)
        path.add_arc(radius=0.25, sweep_deg=90, turn='L')
        path.add_straight(0.36)
        path.add_arc(radius=0.65, sweep_deg=90, turn='R')
        path.add_straight(0.15)
        path.add_arc(radius=0.65, sweep_deg=45, turn='R')
        path.add_straight(0.48)
        path.add_arc(radius=0.25, sweep_deg=45, turn='L')
        path.add_straight(0.47)
        path.hard_turn(angle=45,turn='L')
        path.add_straight(0.14)
        path.hard_turn(angle=45,turn='L')
        path.add_straight(1.98)
        path.hard_turn(angle=90,turn='R')
        path.add_straight(6.64)
        path.hard_turn(angle=90,turn='R')
        path.add_straight(7.16)
        path.hard_turn(angle=90,turn='R')
        path.add_straight(6.64)
        path.hard_turn(angle=90,turn='R')
        path.add_straight(1.98)
        path.hard_turn(angle=45,turn='L')
        path.add_straight(0.14)
        path.hard_turn(angle=45,turn='L')
        path.add_straight(0.96)
        path.add_arc(radius=4.19, sweep_deg=90, turn='R')
        path.add_straight(4.90)
        path.hard_turn(angle=90,turn='L')
        path.add_straight(3)
        path.hard_turn(angle=90,turn='L')
        path.add_straight(15)
        path.hard_turn(angle=90,turn='L')
        path.add_straight(24)
        path.hard_turn(angle=90,turn='L')
        path.add_straight(27.87)

        pts = path.get_points()
        x_coords, y_coords = pts[:,0], pts[:,1]
        x_coords, y_coords = self.rotate(x=x_coords, y=y_coords, theta=theta)
        x_coords, y_coords = self.translate(x=x_coords, y=y_coords, x_translate=-6.65+x, y_translate=17.05+y)

        patch.AddLinPoly(
            points=[x_coords, y_coords],
            norm_dir='z',
            elevation=0,
            length=self.patch_thickness+self.substrate_thickness
        )
        self.gnd = patch
        return
    # ===================== Setters and Getters =====================
    def set_antenna_excitation(self, antenna="TX1", excite=0.0):
        if antenna in ["RX1", "RX2", "RX3", "TX1", "TX2"]:
            self.ports[antenna[:2]][antenna].excite = excite
            return True
        else:
            raise ValueError('antenna must be in the list ["RX1", "RX2", "RX3", "TX1", "TX2"]')
    
    def set_all_antenna_excitation(self, excite=0.0):
        L = ["RX1", "RX2", "RX3", "TX1", "TX2"]
        for elt in L:
            self.set_antenna_excitation(antenna=elt, excite=excite)
        return True
    
    def get_antenna_excitation(self, antenna="TX1"):
        if antenna in ["RX1", "RX2", "RX3", "TX1", "TX2"]:
            return self.ports[antenna[:2]][antenna].excite
        else:
            raise ValueError('antenna must be in the list ["RX1", "RX2", "RX3", "TX1", "TX2"]')

class ElectromagneticSim:
    def __init__(
            self,
            Sim_Path = os.path.join(tempfile.gettempdir(), 'Simp_Patch'),
            DeltaUnit = 1e-3, # Unit of the simulation (everything in millimeters by default)
            SimBox_x = 15,
            SimBox_y = 20,
            SimBox_z = 12,
            NrTS = 30000, # max. number of timesteps to simulate (e.g. default=1e9) ## * Limit the simulation to 30k timesteps
            EndCriteria = 1e-3, # end criteria, e.g. 1e-5, simulations stops if energy has decayed by this value (<1e-4 is recommended, default=1e-5)
            ## * Define a reduced end criteria of -40dB
            post_proc_only=False,
            patch_width= 1.294, # Locked
            patch_length = 1.666, # Locked
            patch_thickness = 0.0406, # Locked
            feed_length=1.25,
            feed_width=0.2,
            q_w_t_width=0.3,
            q_w_t_length=1.25,
            interpatch_length=2.498, # Locked
            inter_feed_width=0.1,
            quarter_wave_transformer = False,
            delta_x=0.333,
            delta_y=0.111,
            spacing_x = 2.498, # Locked
            spacing_y = 2.498, # Locked
            rx_tx_spacing_x=11.8, # Locked
            rx_tx_spacing_y=5.3, # Locked
            substrate_epsR = 3.3, # Locked
            substrate_width = 2.4, 
            substrate_length = 3, 
            substrate_thickness = 0.127, # Locked
            substrate_cells = 4,
            feed_R = 50,  # Locked
            feedpos=-0.47,
            f0 = 60.5e9, # Locked
            fc = 15e9, # 20 dB corner frequency
            show_geometry=True,
            antennas_to_excite = {
                "TX1":1,
                "TX2":1,
            }
        ):

        ### General parameter setup
        self.Sim_Path = Sim_Path
        os.makedirs(self.Sim_Path, exist_ok=True)


        self.post_proc_only = post_proc_only
        self.SimBox = np.array([SimBox_x, SimBox_y, SimBox_z]) # size of the simulation box
        self.DeltaUnit = DeltaUnit
        self.NrTS = NrTS
        self.EndCriteria = EndCriteria

        # create patch
        self.patch_width=patch_width
        self.patch_length = patch_length
        self.patch_thickness = patch_thickness

        self.interpatch_length = interpatch_length
        self.inter_feed_width = inter_feed_width
        
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.feed_length = feed_length
        self.feed_width = feed_width
        
        # quarter_wave_tranformer
        self.q_w_t_width = q_w_t_width
        self.q_w_t_length = q_w_t_length

        self.quarter_wave_transformer = quarter_wave_transformer

        self.spacing_x = spacing_x
        self.spacing_y = spacing_y
        self.rx_tx_spacing_x = rx_tx_spacing_x
        self.rx_tx_spacing_y = rx_tx_spacing_y

        #substrate setup
        self.substrate_epsR   = substrate_epsR
        self.substrate_kappa  = 0.001 * 2*pi*f0 * EPS0*self.substrate_epsR
        self.substrate_width  = substrate_width
        self.substrate_length = substrate_length
        self.substrate_thickness = substrate_thickness
        self.substrate_cells = substrate_cells

        #setup feeding
        self.feed_R = feed_R
        self.feedpos = feedpos
        self.antennas_to_excite = antennas_to_excite

        # setup FDTD parameter & excitation function
        self.f0 = f0
        self.fc = fc
        self.show_geometry = show_geometry

        self.FDTD_setup()
        return

    def FDTD_setup(self):
        ### FDTD setup
        FDTD = openEMS(NrTS=self.NrTS, EndCriteria=self.EndCriteria)
        
        FDTD.SetGaussExcite(self.f0, self.fc)

        FDTD.SetBoundaryCond( ['MUR', 'MUR', 'MUR', 'MUR', 'MUR', 'MUR'] )
        # FDTD.SetBoundaryCond( ['PML_8', 'PML_8', 'PML_8', 'PML_8', 'PML_8', 'PML_8'] )

        CSX = ContinuousStructure()
        FDTD.SetCSX(CSX)
        mesh = CSX.GetGrid()
        mesh.SetDeltaUnit(self.DeltaUnit) # mm
        mesh_res = C0/(self.f0+self.fc)/self.DeltaUnit/20

        ### Generate properties, primitives and mesh-grid
        #initialize the mesh with the "air-box" dimensions
        mesh.AddLine('x', [-self.SimBox[0]/2, self.SimBox[0]/2])
        mesh.AddLine('y', [-self.SimBox[1]/2, self.SimBox[1]/2])
        mesh.AddLine('z', [-self.SimBox[2]/5, self.SimBox[2]*4/5] )

        antennas_to_excite = self.antennas_to_excite

        blackwaves_radar = BlackWavesRadar(
            FDTD=FDTD,
            CSX=CSX,
            patch_width=self.patch_width, 
            patch_length=self.patch_length,
            patch_thickness=self.patch_thickness,
            delta_x=self.delta_x,
            delta_y=self.delta_y,
            feed_length=self.feed_length,
            feed_width=self.feed_width,
            q_w_t_width= self.q_w_t_width,
            q_w_t_length = self.q_w_t_length,
            interpatch_length=self.interpatch_length,
            inter_feed_width=self.inter_feed_width,
            substrate_thickness=self.substrate_thickness,
            spacing_x=self.spacing_x,
            spacing_y=self.spacing_y,
            rx_tx_spacing_x=self.rx_tx_spacing_x, 
            rx_tx_spacing_y=self.rx_tx_spacing_y,
            antennas_to_excite=antennas_to_excite
            )

        RXTX = blackwaves_radar.create_antenna(x=0,y=-3, z=self.substrate_thickness, quarter_wave_transformer=self.quarter_wave_transformer)
        

        # Add cells near the patches
        metal_edge_res = mesh_res/2
        FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.TX.TX1.patch, metal_edge_res=metal_edge_res)
        FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.TX.TX2.patch, metal_edge_res=metal_edge_res)
        FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.RX.RX1.patch, metal_edge_res=metal_edge_res)
        FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.RX.RX2.patch, metal_edge_res=metal_edge_res)
        FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.RX.RX3.patch, metal_edge_res=metal_edge_res)


        epsilon = 0.0
        nb_cells = 2
        y_mesh = -3-self.rx_tx_spacing_x/2+2.5 + self.spacing_x/2
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))
        
        y_mesh = -3-self.rx_tx_spacing_x/2+2.5 - self.spacing_x/2
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))
        
        y_mesh = -3+self.rx_tx_spacing_x/2+2.5 + self.spacing_x
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))
        
        y_mesh = -3 + self.rx_tx_spacing_x/2+2.5
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))
        
        y_mesh = -3 + self.rx_tx_spacing_x/2+2.5 - self.spacing_x
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))
        #FDTD.AddEdges2Grid(dirs='xyz', properties=RXTX.anti_coupler, metal_edge_res=metal_edge_res)

        mesh.AddLine('z', linspace(self.substrate_thickness,self.substrate_thickness+self.patch_thickness,self.substrate_cells+1))
        
        start_x = -0.9*self.SimBox[0]/2
        end_x =  0.9*self.SimBox[0]/2
        start_y = -0.9*self.SimBox[1]/2
        end_y = 0.9*self.SimBox[1]/2

        # create substrate
        substrate = CSX.AddMaterial( 'substrate', epsilon=self.substrate_epsR, kappa=self.substrate_kappa)
        start = [start_x, start_y, 0]
        stop  = [ end_x, end_y, self.substrate_thickness]
        substrate.AddBox( priority=0, start=start, stop=stop )

        # add extra cells to discretize the substrate thickness
        mesh.AddLine('z', linspace(0,self.substrate_thickness,self.substrate_cells+1))

        # create ground (same size as substrate)
        gnd = CSX.AddMetal( 'gnd' ) # create a perfect electric conductor (PEC)
        start[2]=0
        stop[2] =0
        gnd.AddBox(start, stop, priority=10)
        blackwaves_radar.create_gnd_patch(x=0,y=-3,patch=gnd, theta=np.pi/2)
        mesh.AddLine('y', linspace(y_mesh-self.inter_feed_width/2-epsilon/2,y_mesh+self.inter_feed_width/2+epsilon/2,nb_cells))

        # Add cells for the ground
        FDTD.AddEdges2Grid(dirs='xy', properties=gnd)

        # create the pla casing
        tan_delta = 0.07
        epsilon_0 = EPS0
        epsilon_r = 3.0
        omega = 60e9/(2*np.pi)
        kappa = tan_delta * epsilon_0 * epsilon_r * omega

        pla_casing = CSX.AddMaterial( 'PLA_casing', epsilon=epsilon_r, kappa=kappa)
        PLA_casing_thickness = 2.00 #mm
        PLA_casing_distance_from_antennas = 5.00 # mm
        PLA_z_end = PLA_casing_distance_from_antennas + PLA_casing_thickness

        start_x = -0.9*self.SimBox[0]/2
        end_x =  0.9*self.SimBox[0]/2
        start_y = -0.9*self.SimBox[1]/2
        end_y = 0.9*self.SimBox[1]/2

        start = [start_x, start_y, PLA_casing_distance_from_antennas]
        stop  = [end_x, end_y, PLA_z_end]
        pla_casing.AddBox( priority=8, start=start, stop=stop)
        mesh.AddLine('z', linspace(PLA_casing_distance_from_antennas-0.2,PLA_casing_distance_from_antennas+0.2,10))

        # create a reflector
        reflector = CSX.AddMaterial( 'reflector', epsilon=1.0, kappa=1e7, mue=10000)
        reflector_thickness = 1.500 #mm

        start_x = -0.9*self.SimBox[0]/2
        end_x =  0.9*self.SimBox[0]/2
        start_y = -0.9*self.SimBox[1]/2
        end_y = 0.9*self.SimBox[1]/2

        start = [start_x, start_y, PLA_z_end]
        stop  = [ end_x, end_y, PLA_z_end + reflector_thickness]
        reflector.AddBox( priority=8, start=start, stop=stop)
        mesh.AddLine('z', linspace(PLA_z_end-0.2,PLA_z_end+0.2,10))

        
        # Set excitation levels for the antennas
        ports = blackwaves_radar.ports
        blackwaves_radar.set_all_antenna_excitation(0.0)
        blackwaves_radar.set_antenna_excitation("TX1",1.0)
        # blackwaves_radar.set_antenna_excitation("TX2",-1.0)        

        mesh.SmoothMeshLines('all', mesh_res, 1.4)

        # Add the nf2ff recording box
        nf2ff = FDTD.CreateNF2FFBox()

        if self.show_geometry:
            CSX.Write2XML('geometry.xml')
            os.system('AppCSXCAD geometry.xml')
        
        self.CSX = CSX
        self.FDTD = FDTD
        self.ports = ports
        self.nf2ff = nf2ff
        return

    def run(self):
        Sim_Path = self.Sim_Path
        post_proc_only = self.post_proc_only
        
        CSX = self.CSX
        FDTD = self.FDTD
        
        ### Run the simulation
        if 0:  # debugging only
            CSX_file = os.path.join(Sim_Path, 'simp_patch.xml')
            if not os.path.exists(Sim_Path):
                os.mkdir(Sim_Path)
            CSX.Write2XML(CSX_file)
            from CSXCAD import AppCSXCAD_BIN
            os.system(AppCSXCAD_BIN + ' "{}"'.format(CSX_file))

        if not post_proc_only:
            FDTD.Run(Sim_Path, verbose=0, cleanup=True)

    def calculate_antenna_caracteristics(self):
        f0 = self.f0
        fc = self.fc
        ports = self.ports
        nf2ff = self.nf2ff
        Sim_Path = self.Sim_Path

        port_TX1 = ports["TX"]["TX1"]

        ### Post-processing and plotting
        f = np.linspace(max(1e9,f0-fc),f0+fc,401)
        
        port_TX1.CalcPort(Sim_Path, f)
        s11 = port_TX1.uf_ref/port_TX1.uf_inc
        s11_dB = 20.0*np.log10(np.abs(s11))
        
        figure()
        plot(f/1e9, s11_dB, 'k-', linewidth=2, label='$S_{11}$')
        grid()
        legend()
        ylabel('S-Parameter (dB)')
        xlabel('Frequency (GHz)')

        idx = np.where((s11_dB<-7) & (s11_dB==np.min(s11_dB)))[0]
        if not len(idx)==1:
            print('No resonance frequency found for far-field calulation')
        else:
            f_res = f[idx[0]]
            # print(f_res)
            f_res = 62000000000.0
            theta = np.arange(-180.0, 180.0, 2.0)
            phi   = [0., 90.]
            nf2ff_res = nf2ff.CalcNF2FF(Sim_Path, f_res, theta, phi, center=[0,0,1e-3])

            figure()
            E_norm = 20.0*np.log10(nf2ff_res.E_norm[0]/np.max(nf2ff_res.E_norm[0])) + nf2ff_res.Dmax[0]
            plot(theta, np.squeeze(E_norm[:,0]), 'k-', linewidth=2, label='xz-plane')
            plot(theta, np.squeeze(E_norm[:,1]), 'r--', linewidth=2, label='yz-plane')
            grid()
            ylabel('Directivity (dBi)')
            xlabel('Theta (deg)')
            title('Frequency: {} GHz'.format(f_res/1e9))
            legend()

        Zin = port_TX1.uf_tot/port_TX1.if_tot
        figure()
        plot(f/1e9, np.real(Zin), 'k-', linewidth=2, label='$\Re\{Z_{in}\}$')
        plot(f/1e9, np.imag(Zin), 'r--', linewidth=2, label='$\Im\{Z_{in}\}$')
        grid()
        legend()
        ylabel('Zin (Ohm)')
        xlabel('Frequency (GHz)')

        show()

    def show_voltage_static(self):
        f0 = self.f0
        fc = self.fc
        ports = self.ports
        Sim_Path = self.Sim_Path

        port_TX1 = ports["TX"]["TX1"]
        port_TX2 = ports["TX"]["TX2"]

        port_RX1 = ports["RX"]["RX1"]
        port_RX2 = ports["RX"]["RX2"]
        port_RX3 = ports["RX"]["RX3"]
        
        # ### Post-processing and plotting
        f = np.linspace(max(1e9,f0-fc),f0+fc,401)

        port_TX1.CalcPort(Sim_Path, f)
        port_TX2.CalcPort(Sim_Path, f)

        figure()

        # First subplot for transmitting ports (TX)
        subplot(2, 1, 1)
        plot(port_TX1.u_data.ui_time[0], port_TX1.ut_tot, 'k-', linewidth=2, label='$U_{TX1}$')
        plot(port_TX2.u_data.ui_time[0], port_TX2.ut_tot, 'b-', linewidth=2, label='$U_{TX2}$')
        grid()
        legend()
        title('Tension aux bornes des ports émetteurs')
        ylabel('Voltage')

        # Second subplot for receiving ports (RX)
        subplot(2, 1, 2)
        port_RX1.CalcPort(Sim_Path, f)
        port_RX2.CalcPort(Sim_Path, f)
        port_RX3.CalcPort(Sim_Path, f)
        plot(port_RX1.u_data.ui_time[0], port_RX1.ut_tot, 'r-', linewidth=2, label='$U_{RX1}$')
        plot(port_RX2.u_data.ui_time[0], port_RX2.ut_tot, 'c-', linewidth=2, label='$U_{RX2}$')
        plot(port_RX3.u_data.ui_time[0], port_RX3.ut_tot, 'm-', linewidth=2, label='$U_{RX3}$')
        grid()
        legend()
        title('Tension aux bornes des ports récepteurs')
        ylabel('Voltage')
        xlabel('Time')

        show()
        
    def show_voltage_animated(self, save=False):
        f0 = self.f0
        fc = self.fc
        ports = self.ports
        nf2ff = self.nf2ff
        Sim_Path = self.Sim_Path

        port_TX1 = ports["TX"]["TX1"]
        port_TX2 = ports["TX"]["TX2"]

        port_RX1 = ports["RX"]["RX1"]
        port_RX2 = ports["RX"]["RX2"]
        port_RX3 = ports["RX"]["RX3"]
        
        # ### Post-processing and plotting
        f = np.linspace(max(1e9,f0-fc),f0+fc,401)

        port_TX1.CalcPort(Sim_Path, f)
        port_TX2.CalcPort(Sim_Path, f)
        
        # Prepare data
        port_RX1.CalcPort(Sim_Path, f)
        port_RX2.CalcPort(Sim_Path, f)
        port_RX3.CalcPort(Sim_Path, f)

        # Get time arrays
        time_TX1 = port_TX1.u_data.ui_time[0]
        # print(time_TX1)

        time_TX2 = port_TX2.u_data.ui_time[0]
        time_RX1 = port_RX1.u_data.ui_time[0]
        time_RX2 = port_RX2.u_data.ui_time[0]
        time_RX3 = port_RX3.u_data.ui_time[0]

        # Create figure and subplots
        fig, (ax1, ax2) = subplots(2, 1, figsize=(10, 8))

        # Initialize lines for TX
        line_TX1, = ax1.plot([], [], 'k-', linewidth=2, label='$U_{TX1}$')
        line_TX2, = ax1.plot([], [], 'b-', linewidth=2, label='$U_{TX2}$')
        ax1.set_xlim(min(time_TX1), max(time_TX1))
        ax1.set_ylim(min(min(port_TX1.ut_tot), min(port_TX2.ut_tot)) * 1.1, 
                    max(max(port_TX1.ut_tot), max(port_TX2.ut_tot)) * 1.1)
        ax1.grid()
        ax1.legend()
        ax1.set_title('Tension aux bornes des ports émetteurs')
        ax1.set_ylabel('Voltage')

        # Initialize lines for RX
        line_RX1, = ax2.plot([], [], 'r-', linewidth=2, label='$U_{RX1}$')
        line_RX2, = ax2.plot([], [], 'c-', linewidth=2, label='$U_{RX2}$')
        line_RX3, = ax2.plot([], [], 'm-', linewidth=2, label='$U_{RX3}$')
        ax2.set_xlim(min(time_RX1), max(time_RX1))
        ax2.set_ylim(min(min(port_RX1.ut_tot), min(port_RX2.ut_tot), min(port_RX3.ut_tot)) * 1.1,
                    max(max(port_RX1.ut_tot), max(port_RX2.ut_tot), max(port_RX3.ut_tot)) * 1.1)
        ax2.grid()
        ax2.legend()
        ax2.set_title('Tension aux bornes des ports récepteurs')
        ax2.set_ylabel('Voltage')
        ax2.set_xlabel('Time')

        # Animation function
        def animate(frame):
            # Update TX lines
            line_TX1.set_data(time_TX1[:frame], port_TX1.ut_tot[:frame])
            line_TX2.set_data(time_TX2[:frame], port_TX2.ut_tot[:frame])
            
            # Update RX lines
            line_RX1.set_data(time_RX1[:frame], port_RX1.ut_tot[:frame])
            line_RX2.set_data(time_RX2[:frame], port_RX2.ut_tot[:frame])
            line_RX3.set_data(time_RX3[:frame], port_RX3.ut_tot[:frame])
            
            return line_TX1, line_TX2, line_RX1, line_RX2, line_RX3

        # Create animation
        num_frames = min(len(time_TX1), len(time_RX1))
        anim = FuncAnimation(fig, animate, frames=num_frames, interval=20, blit=True, repeat=False)
        
        # Save animation as MP4
        if save:
            writer = FFMpegWriter(fps=30, bitrate=1800)
            anim.save('port_voltages_animation.mp4', writer=writer, dpi=150)
            print("Animation saved as 'port_voltages_animation.mp4'")


        show()
    
    def calculate_transfer_function(self, show_graph=False):
        """
        Docstring for calculate_transfer_function
        This function calculates the transfer function

        :param self: Description
        """

        ports = self.ports
        Sim_Path = self.Sim_Path
        f0 = self.f0
        fc = self.fc
        
        port_TX1 = ports["TX"]["TX1"]
        port_TX2 = ports["TX"]["TX2"]

        port_RX1 = ports["RX"]["RX1"]
        port_RX2 = ports["RX"]["RX2"]
        port_RX3 = ports["RX"]["RX3"]

        f = np.linspace(max(1e9,f0-fc/2),f0+fc/2,401)
        port_TX1.CalcPort(Sim_Path, f)
        port_TX2.CalcPort(Sim_Path, f)
        port_RX1.CalcPort(Sim_Path, f)
        port_RX2.CalcPort(Sim_Path, f)
        port_RX3.CalcPort(Sim_Path, f)

        g_tx1_rx1 = port_RX1.uf_tot/port_TX1.uf_tot
        g_tx1_rx1_dB = 20.0*np.log10(np.abs(g_tx1_rx1))
        phi_tx1_rx1 = np.degrees(np.unwrap(np.angle(g_tx1_rx1)))

        g_tx1_rx2 = port_RX2.uf_tot/port_TX1.uf_tot
        g_tx1_rx2_dB = 20.0*np.log10(np.abs(g_tx1_rx2))
        phi_tx1_rx2 = np.degrees(np.unwrap(np.angle(g_tx1_rx2)))

        g_tx1_rx3 = port_RX3.uf_tot/port_TX1.uf_tot
        g_tx1_rx3_dB = 20.0*np.log10(np.abs(g_tx1_rx3))
        phi_tx1_rx3 = np.degrees(np.unwrap(np.angle(g_tx1_rx3)))

        g_tx2_rx1 = port_RX1.uf_tot/port_TX2.uf_tot
        g_tx2_rx1_dB = 20.0*np.log10(np.abs(g_tx2_rx1))
        phi_tx2_rx1 = np.degrees(np.unwrap(np.angle(g_tx2_rx1)))

        g_tx2_rx2 = port_RX2.uf_tot/port_TX2.uf_tot
        g_tx2_rx2_dB = 20.0*np.log10(np.abs(g_tx2_rx2))
        phi_tx2_rx2 = np.degrees(np.unwrap(np.angle(g_tx2_rx2)))

        g_tx2_rx3 = port_RX3.uf_tot/port_TX2.uf_tot
        g_tx2_rx3_dB = 20.0*np.log10(np.abs(g_tx2_rx3))
        phi_tx2_rx3 = np.degrees(np.unwrap(np.angle(g_tx2_rx3)))
        
        if show_graph : 
            fig, (ax1, ax2) = subplots(2, 1, figsize=(10, 8))

            ax1.plot(f/1e9, g_tx1_rx1_dB, 'k-', linewidth=2, label='$G_{TX_1, RX_1}$')
            ax2.plot(f/1e9, phi_tx1_rx1, 'k-', linewidth=2, label='$Phi_{TX_1, RX_1}$')

            ax1.plot(f/1e9, g_tx1_rx2_dB, 'r-', linewidth=2, label='$G_{TX_1, RX_2}$')
            ax2.plot(f/1e9, phi_tx1_rx2, 'r-', linewidth=2, label='$Phi_{TX_1, RX_2}$')

            ax1.plot(f/1e9, g_tx1_rx3_dB, 'b-', linewidth=2, label='$G_{TX_1, RX_3}$')
            ax2.plot(f/1e9, phi_tx1_rx3, 'b-', linewidth=2, label='$Phi_{TX_1, RX_3}$')

            ax1.plot(f/1e9, g_tx2_rx1_dB, 'c-', linewidth=2, label='$G_{TX_2, RX_1}$')
            ax2.plot(f/1e9, phi_tx2_rx1, 'c-', linewidth=2, label='$Phi_{TX_2, RX_1}$')

            ax1.plot(f/1e9, g_tx2_rx2_dB, 'm-', linewidth=2, label='$G_{TX_2, RX_2}$')
            ax2.plot(f/1e9, phi_tx2_rx2, 'm-', linewidth=2, label='$Phi_{TX_2, RX_2}$')

            ax1.plot(f/1e9, g_tx2_rx3_dB, 'g-', linewidth=2, label='$G_{TX_2, RX_3}$')
            ax2.plot(f/1e9, phi_tx2_rx3, 'g-', linewidth=2, label='$Phi_{TX_2, RX_3}$')
            ax1.grid()
            ax2.grid()
            ax1.legend()
            ax2.legend()
            fig.suptitle('Diagramme de Bode')
            ax1.set_ylabel('Gain (dB)')
            ax2.set_ylabel('Phase (°)')
            ax1.set_xlabel('Frequency (GHz)')
            ax2.set_xlabel('Frequency (GHz)')
        
            show()

        big_array = np.array([g_tx1_rx1,g_tx1_rx2,g_tx1_rx3,g_tx2_rx1,g_tx2_rx2, g_tx2_rx3])
        
        return {"frequencies":f,"transfer_function_array": big_array}

        return
    
class TransferFunctionIdentifier:
    def __init__(
            self,
            electromagnetic_sim_plus:ElectromagneticSim, 
            electromagnetic_sim_moins:ElectromagneticSim,
            force_run_sim=False
        ):

        self.tx1_plus_tx2_sim = electromagnetic_sim_plus

        self.tx1_moins_tx2_sim = electromagnetic_sim_moins

        self.tx1_plus_tx2_sim.FDTD_setup()
        self.tx1_moins_tx2_sim.FDTD_setup()

        if force_run_sim:
            self.tx1_plus_tx2_sim.run()
            self.tx1_moins_tx2_sim.run()

        
        return
    
    def calculate_transfer_function(self, show_graph=False):
        """
        Docstring for calculate_transfer_function

        Returns the complex (6x401) array that defines how a material reflects frequencies from the TX to the RX
        antennas. The array returned
        
        :param self: Description
        :param show_graph: Description
        """

        self.t_plus = self.tx1_plus_tx2_sim.calculate_transfer_function(show_graph=show_graph)
        self.t_moins = self.tx1_moins_tx2_sim.calculate_transfer_function(show_graph=show_graph)
        
        return {
            "frequencies":self.t_plus["frequencies"],
            "transfer_function_array_+": self.t_plus["transfer_function_array"],
            "transfer_function_array_-": self.t_moins["transfer_function_array"]}


if __name__ == "__main__" :

    tx1_plus_tx2_sim = ElectromagneticSim(
        Sim_Path=os.path.join(tempfile.gettempdir(), 'test1', 'tx1_plus_tx2'),
        antennas_to_excite={
            "TX1":1,
            "TX2":1,
        },
        show_geometry=True
    )

    # tfi = TransferFunctionIdentifier(force_run_sim=False)
    # print(tfi.calculate_transfer_function())