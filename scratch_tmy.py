import pvlib
from pvlib import iotools
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import pandas as pd

lat, lon = 13.75, 100.51

# 1. Fetch TMY
print("Fetching TMY...")
tmy_data = iotools.get_pvgis_tmy(lat, lon, map_variables=True)[0]

# 2. Localize and Sort
tmy_data.index = tmy_data.index.tz_convert('Asia/Bangkok')
tmy_data['month'] = tmy_data.index.month
tmy_data['day'] = tmy_data.index.day
tmy_data['hour'] = tmy_data.index.hour
tmy_data = tmy_data.sort_values(['month', 'day', 'hour'])

# Override index to 2023 timezone-aware
yearly_index_tz = pd.date_range(start='2023-01-01 00:00', end='2023-12-31 23:00', freq='1H', tz='Asia/Bangkok')
tmy_data.index = yearly_index_tz

# 3. Setup System
location = Location(latitude=lat, longitude=lon, tz='Asia/Bangkok')
system = PVSystem(
    surface_tilt=15,
    surface_azimuth=180,
    module_parameters={'pdc0': 120000, 'gamma_pdc': -0.0035},
    inverter_parameters={'pdc0': 100000 / 0.96, 'pac0': 100000, 'eta_inv_nom': 0.96},
    temperature_model_parameters=TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
)

mc = ModelChain(system, location, 
                aoi_model='physical', spectral_model='no_loss', 
                dc_model='pvwatts', ac_model='pvwatts', losses_model='pvwatts')

print("Running simulation...")
mc.run_model(tmy_data)
pv_ac = mc.results.ac
print("Total AC Generation (kWh/year):", pv_ac.sum() / 1000)
print("Max AC Power (kW):", pv_ac.max() / 1000)
