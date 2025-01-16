const select = document.getElementById('detector_selection');

select.addEventListener('change', function handleChange(event) {
  let detector_data = JSON.parse(event.target.value.replace(/"/g, '\\"').replaceAll("'", '"'))
  const det_input = document.getElementById('detector_div')
  det_input.style.display = 'block'
  const det_name = document.getElementById('detector_name')
  det_name.value = detector_data.name
  const det_tone = document.getElementById('detector_tones')
  det_tone.value = detector_data.tones
  const det_match_threshold = document.getElementById('detector_match_threshold')
  det_match_threshold.value = detector_data.matchThreshold
  const det_tolerance_percent = document.getElementById('detector_tolerance_percent')
  det_tolerance_percent.value = detector_data.tolerancePercent

  const det_pushbullet_select = document.getElementById('detector_pushbullet_selection')
  det_pushbullet_select.innerText = null;
  let pb = document.createElement("option");
  pb.textContent = "Edit Pushbullet"
  det_pushbullet_select.appendChild(pb);
  for(let i = 0; i < detector_data.notifications.preRecording.pushbullet.length; i++) {
    let opt = detector_data.notifications.preRecording.pushbullet[i]["title"];
    let el = document.createElement("option");
    el.textContent = opt;
    el.value = JSON.stringify(detector_data.notifications.preRecording.pushbullet[i]);
    det_pushbullet_select.appendChild(el);
  }
  let npb = document.createElement("option");
  npb.textContent = "Add New Pushbullet"
  npb.value = "new_pushbullet"
  det_pushbullet_select.appendChild(npb);
  const det_pushbullet_full = document.getElementById('detector_pushbullet_full')
  det_pushbullet_full.value = JSON.parse(detector_data.notifications.preRecording.pushbullet)

});

const pbselect = document.getElementById('detector_pushbullet_selection');

pbselect.addEventListener('change', function handleChange(event) {
  let pushover_data = JSON.parse(event.target.value)


});

