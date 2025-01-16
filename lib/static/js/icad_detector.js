const detector_select = document.getElementById('detector_selection');

detector_select.addEventListener('change', function handleChange(event) {
  const name = this.options[this.selectedIndex].getAttribute('name')
  if (name === "new_detector"){
    console.log(event.target.value)
    let detector_data = JSON.parse(event.target.value.replace(/"/g, '\\"').replaceAll("'", '"'))
    add_new_detector(detector_data)
  } else if (name === "none") {
    const det_input = document.getElementById('detector_input_div')
    det_input.style.display = 'none'
  } else {
    let detector_data = JSON.parse(event.target.value.replace(/"/g, '\\"').replaceAll("'", '"'))
    show_detector_input(detector_data)
  }

});

function show_detector_input(detector_data){
  const det_input = document.getElementById('detector_input_div')
  det_input.style.display = 'block'
  const det_id = document.getElementById('detector_id')
  det_id.value = detector_data.detector_id
  const det_name = document.getElementById('detector_name')
  det_name.value = detector_data.name
  const det_tone = document.getElementById('detector_tones')
  det_tone.value = detector_data.tones
  const det_match_threshold = document.getElementById('detector_tolerance')
  det_match_threshold.value = detector_data.tone_tolerance
  const det_ignore_time = document.getElementById('detector_ignore_time')
  det_ignore_time.value = detector_data.ignore_time
}

function add_new_detector(new_detector_template) {
  const det_input = document.getElementById('detector_input_div')
  det_input.style.display = 'block'
  const det_id = document.getElementById('detector_id')
  det_id.value = new_detector_template.detector_id
  const det_name = document.getElementById('detector_name')
  det_name.value = new_detector_template.name
  const det_tone = document.getElementById('detector_tones')
  det_tone.value = new_detector_template.tones
  const det_match_threshold = document.getElementById('detector_match_threshold')
  det_match_threshold.value = new_detector_template.matchThreshold
  const det_tolerance_percent = document.getElementById('detector_tolerance_percent')
  det_tolerance_percent.value = new_detector_template.tolerancePercent
}

function populate_detectors(detector_data) {
  const detector_select = document.getElementById('detector_selection')
  detector_select.innerText = null;
  let detector_select_default = document.createElement("option");
  detector_select_default.textContent = "Select Detector"
  detector_select.appendChild(detector_select_default);
  for(let i = 0; i < detector_data.length; i++) {
      detector_ids.push(detector_data[i]["detector_id"])
    let opt = detector_data[i]["name"];
    let el = document.createElement("option");
    el.textContent = opt;
    el.value = JSON.stringify(detector_data[i]["detector_id"]);
    detector_select.appendChild(el);
  }
  let create_new_detector = document.createElement("option");
  create_new_detector.textContent = "Add New Detector"
  create_new_detector.value = "new_detector"
  detector_select.appendChild(create_new_detector);

}