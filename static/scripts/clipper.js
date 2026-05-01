import WaveSurfer from "https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js";

let streamid = 0;
let audioid = "";

const items = [
	{ name: "LR-OB1", url: "https://ingest.radio.roses.media:8443/LR-OB1" },
	{ name: "LR-OB2", url: "https://ingest.radio.roses.media:8443/LR-OB2" },
	{ name: "LR-OB3", url: "https://ingest.radio.roses.media:8443/LR-OB3" },
	{ name: "LR-OB4", url: "https://ingest.radio.roses.media:8443/LR-OB4" },
	{ name: "LR-OB5", url: "https://ingest.radio.roses.media:8443/LR-OB5" },
	{ name: "LR-OBD", url: "https://ingest.radio.roses.media:8443/LR-OBD" },
	{ name: "YR-OB0", url: "https://ingest.radio.roses.media:8443/YR-OB0" },
	{ name: "YR-OB1", url: "https://ingest.radio.roses.media:8443/YR-OB1" },
	{ name: "YR-OB2", url: "https://ingest.radio.roses.media:8443/YR-OB2" },
	{ name: "YR-OB3", url: "https://ingest.radio.roses.media:8443/YR-OB3" },
	{ name: "YR-OB4", url: "https://ingest.radio.roses.media:8443/YR-OB4" },
	{ name: "CR-OB0", url: "https://ingest.radio.roses.media:8443/CR-OB0" },
];

function populateDropdown(dataList) {
	const select = document.getElementById("nameSelect");
	const input = document.getElementById("streamurl");

	// Clear existing options
	select.innerHTML = "";

	// Create and append options
	dataList.forEach((item) => {
		const option = document.createElement("option");
		option.value = item.url;
		option.textContent = item.name;
		select.appendChild(option);
	});

	// Set initial input value if there are items
	if (dataList.length > 0) {
		input.value = dataList[0].url;
	}

	// Event listener for selection change
	select.addEventListener("change", function () {
		input.value = this.value;
	});
}

populateDropdown(items);

function timeToString(time) {
	let minutes = Math.floor(time / 60);
	let seconds = Math.floor(time % 60);
	minutes = (minutes < 10 ? "0" : "") + minutes;
	seconds = (seconds < 10 ? "0" : "") + seconds;
	return minutes + ":" + seconds;
}

function stringToTime(time) {
	let times = time.split(":");
	let seconds = Number(times[0]) * 60 + Number(times[1]);
	return seconds;
}

function StartRec() {
	document.getElementById("clipper").style.display = "none";
	document.getElementById("loading").style.display = "none";
	document.getElementById("exporter").style.display = "none";
	document.getElementById("error").style.display = "none";
	document.getElementById("exported").style.display = "none";
	let streamurl = document.getElementById("streamurl").value;
	console.log(streamurl);
	const api_url = "/clipper/startrecording";
	fetch(api_url, {
		method: "POST",
		body: JSON.stringify({
			url: streamurl,
		}),
		headers: {
			"Content-type": "application/json; charset=UTF-8",
		},
	})
		.then((response) => {
			return response.json();
		})
		.then((data) => {
			console.log(data["uid"]);
			streamid = data["uid"];
		});
}

function updateState() {
	if (streamid != 0) {
		const api_url = "/clipper/getstate/" + streamid;
		fetch(api_url)
			.then((response) => {
				return response.json();
			})
			.then((data) => {
				setState(data["state"]);
			})
			.catch((error) => {
				setState("conerror");
			});
	}
}

function setState(state) {
	document.getElementById("clippinger").style.display = "block";
	document.getElementById("recording").style.display = "none";
	document.getElementById("paused").style.display = "none";
	document.getElementById("closed").style.display = "none";
	document.getElementById("conerror").style.display = "none";
	document.getElementById(state).style.display = "block";
}

function makeaudio(time) {
	if (streamid != 0) {
		document.getElementById("clipper").style.display = "none";
		document.getElementById("exporter").style.display = "none";
		document.getElementById("loading").style.display = "block";
		document.getElementById("error").style.display = "none";
		document.getElementById("exported").style.display = "none";
		const api_url = "/clipper/makeaudio/" + streamid + "/" + time;
		fetch(api_url)
			.then((response) => {
				return response.json();
			})
			.then((data) => {
				console.log(data["uid"]);
				audioid = data["uid"];
				wavesurfer.load("/clipper/getaudio/" + audioid);
				document.getElementById("clipper").style.display = "block";
				document.getElementById("exporter").style.display = "none";
				document.getElementById("loading").style.display = "none";
				document.getElementById("error").style.display = "none";
				document.getElementById("exported").style.display = "none";
			})
			.catch((error) => {
				document.getElementById("clipper").style.display = "none";
				document.getElementById("exporter").style.display = "none";
				document.getElementById("loading").style.display = "none";
				document.getElementById("error").style.display = "block";
				document.getElementById("errormsg").textContent =
					"Error creating clip audio";
				document.getElementById("exported").style.display = "none";
			});
	} else {
		document.getElementById("clipper").style.display = "none";
		document.getElementById("exporter").style.display = "none";
		document.getElementById("loading").style.display = "none";
		document.getElementById("error").style.display = "block";
		document.getElementById("errormsg").textContent =
			"No stream has been defined";
		document.getElementById("exported").style.display = "none";
	}
}

function makeclip(start, end) {
	let apiUrl = "/clipper/makeclip/" + audioid + "/" + start + "/" + end;
	fetch(apiUrl)
		.then((response) => {
			return response.json();
		})
		.then((data) => {
			clipsurfer.load("/clipper/getclip/" + audioid);
			wavesurfer.pause();
			document.getElementById("download").href =
				"/clipper/getclip/" + audioid;
			document.getElementById("exporter").style.display = "block";
			document.getElementById("loading").style.display = "none";
			document.getElementById("exported").style.display = "none";
		})
		.catch((error) => {
			document.getElementById("clipper").style.display = "none";
			document.getElementById("loading").style.display = "none";
			document.getElementById("error").style.display = "block";
			document.getElementById("errormsg").textContent =
				"Error trying to make clip";
			document.getElementById("exported").style.display = "none";
		});
}

function StoreClip() {
	document.getElementById("loading").style.display = "block";
	let streamname = document.getElementById("streamname").value;
	let clipname = document.getElementById("clipname").value;
	if (streamname != "" && clipname != "") {
		const regex = /^[a-z\d\s]+$/i;
		if (regex.test(streamname) && regex.test(clipname)) {
			streamname = streamname.replace(/\s+/g, "-");
			clipname = clipname.replace(/\s+/g, "-");
			console.log(clipname);
			let apiUrl =
				"/clipper/saveclip/" +
				audioid +
				"/" +
				clipname +
				"/" +
				streamname;
			fetch(apiUrl)
				.then((response) => {
					if (!response.ok) {
						throw new Error("Network response was not ok");
					}
					return response.json();
				})
				.then((data) => {
					document.getElementById("cliplink").href =
						"/clips/" + data["uid"];
					document.getElementById("loading").style.display = "none";
					document.getElementById("exported").style.display = "block";
					document.getElementById("error").style.display = "none";
				})
				.catch((error) => {
					document.getElementById("loading").style.display = "none";
					document.getElementById("exported").style.display = "none";
					document.getElementById("error").style.display = "block";
					document.getElementById("errormsg").textContent =
						"Server error when attempting to save clip";
				});
		} else {
			document.getElementById("loading").style.display = "none";
			document.getElementById("exported").style.display = "none";
			document.getElementById("error").style.display = "block";
			document.getElementById("errormsg").textContent =
				"Stream name and clip name must be alphanumeric without special characters";
		}
	} else {
		document.getElementById("loading").style.display = "none";
		document.getElementById("exported").style.display = "none";
		document.getElementById("error").style.display = "block";
		document.getElementById("errormsg").textContent =
			"Stream name and clip name not provided";
	}
}

let wavesurfer = WaveSurfer.create({
	container: "#waveform",
	waveColor: "#a00000",
	progressColor: "#c40000",
	mediaControls: true,
});

let clipsurfer = WaveSurfer.create({
	container: "#clipWaveform",
	waveColor: "#a00000",
	progressColor: "#c40000",
	mediaControls: true,
});

document.getElementById("startrecbtn").addEventListener("click", StartRec);
document.getElementById("storeclip").addEventListener("click", StoreClip);

document.getElementById("clip30").addEventListener(
	"click",
	function () {
		makeaudio("30");
	},
	false,
);
document.getElementById("clip1").addEventListener(
	"click",
	function () {
		makeaudio("1");
	},
	false,
);
document.getElementById("clip2").addEventListener(
	"click",
	function () {
		makeaudio("2");
	},
	false,
);
document.getElementById("clip3").addEventListener(
	"click",
	function () {
		makeaudio("3");
	},
	false,
);
document.getElementById("clip5").addEventListener(
	"click",
	function () {
		makeaudio("5");
	},
	false,
);

document.getElementById("clip30m").addEventListener(
	"click",
	function () {
		makeaudio("30");
	},
	false,
);
document.getElementById("clip1m").addEventListener(
	"click",
	function () {
		makeaudio("1");
	},
	false,
);
document.getElementById("clip2m").addEventListener(
	"click",
	function () {
		makeaudio("2");
	},
	false,
);
document.getElementById("clip5m").addEventListener(
	"click",
	function () {
		makeaudio("5");
	},
	false,
);

document.getElementById("setStart").addEventListener("click", async () => {
	document.getElementById("startClip").value = timeToString(
		wavesurfer.getCurrentTime(),
	);
});

document.getElementById("setEnd").addEventListener("click", async () => {
	document.getElementById("endClip").value = timeToString(
		wavesurfer.getCurrentTime(),
	);
});

document.getElementById("clip").addEventListener("click", async () => {
	document.getElementById("error").style.display = "none";
	document.getElementById("loading").style.display = "block";
	document.getElementById("exporter").style.display = "none";
	document.getElementById("exported").style.display = "none";

	let start = stringToTime(document.getElementById("startClip").value);
	let end = stringToTime(document.getElementById("endClip").value);
	if (start > end) {
		document.getElementById("loading").style.display = "none";
		document.getElementById("exporter").style.display = "none";
		document.getElementById("error").style.display = "block";
		document.getElementById("errormsg").textContent =
			"End time must be after start time";
		document.getElementById("exported").style.display = "none";
	} else {
		makeclip(start, end);
	}
});

//runs every second
function updateloop() {
	updateState();
}

setInterval(updateloop, 1 * 1000);
